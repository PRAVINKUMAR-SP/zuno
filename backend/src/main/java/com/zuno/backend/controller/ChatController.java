package com.zuno.backend.controller;

import com.zuno.backend.dto.ChatRequestDto;
import com.zuno.backend.dto.ChatResponseDto;
import com.zuno.backend.dto.ConversationDto;
import com.zuno.backend.dto.MessageDto;
import com.zuno.backend.dto.RenameConversationDto;
import com.zuno.backend.entity.UserMemory;
import com.zuno.backend.service.AiClientService;
import com.zuno.backend.service.AiClientService.AiStreamResult;
import com.zuno.backend.service.AuthService;
import com.zuno.backend.service.ChatService;
import com.zuno.backend.service.ChatService.PreparedChat;
import com.zuno.backend.service.MemoryService;
import com.zuno.backend.util.AuthUtil;
import jakarta.validation.Valid;
import java.io.IOException;
import java.io.InputStream;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicReference;
import javax.sql.DataSource;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.ObjectMapper;

@RestController
@RequestMapping("/api")
public class ChatController {

    private final ChatService chatService;
    private final AiClientService aiClientService;
    private final MemoryService memoryService;
    private final AuthService authService;
    private final DataSource dataSource;
    private final ObjectMapper objectMapper;
    private final ExecutorService streamExecutor = Executors.newVirtualThreadPerTaskExecutor();

    public ChatController(
            ChatService chatService,
            AiClientService aiClientService,
            MemoryService memoryService,
            AuthService authService,
            DataSource dataSource,
            ObjectMapper objectMapper) {
        this.chatService = chatService;
        this.aiClientService = aiClientService;
        this.memoryService = memoryService;
        this.authService = authService;
        this.dataSource = dataSource;
        this.objectMapper = objectMapper;
    }

    @GetMapping("/health")
    public Map<String, Object> health() {
        boolean dbReady = false;
        try (var conn = dataSource.getConnection()) {
            dbReady = conn.isValid(2);
        } catch (Exception ignored) {
        }

        JsonNode aiHealth = aiClientService.checkHealth();
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("status", dbReady && aiHealth.path("ready").asBoolean(false) ? "ok" : "degraded");
        result.put("database", dbReady ? "connected" : "disconnected");
        result.put("ai", aiHealth);
        return result;
    }

    @GetMapping("/conversations")
    public List<ConversationDto> listConversations(
            @org.springframework.web.bind.annotation.RequestHeader(value = "Authorization", required = false) String authHeader) {
        AuthUtil.TokenInfo info = AuthController.extractTokenInfo(authHeader);
        return chatService.listConversations(info != null ? info.userId() : null);
    }

    @PostMapping("/conversations")
    public ConversationDto createConversation(
            @RequestBody(required = false) Map<String, String> body,
            @org.springframework.web.bind.annotation.RequestHeader(value = "Authorization", required = false) String authHeader) {
        AuthUtil.TokenInfo info = AuthController.extractTokenInfo(authHeader);
        String title = body == null ? "New Chat" : body.getOrDefault("title", "New Chat");
        return chatService.createConversation(title, info != null ? info.userId() : null);
    }

    @PatchMapping("/conversations/{id}")
    public ConversationDto renameConversation(
            @PathVariable Long id,
            @Valid @RequestBody RenameConversationDto body) {
        return chatService.renameConversation(id, body.title());
    }

    @DeleteMapping("/conversations/{id}")
    public void deleteConversation(@PathVariable Long id) {
        chatService.deleteConversation(id);
    }

    @GetMapping("/conversations/{id}/messages")
    public List<MessageDto> getMessages(@PathVariable Long id) {
        return chatService.getMessages(id);
    }

    @GetMapping("/memories")
    public List<UserMemory> listMemories() {
        return memoryService.listMemories();
    }

    @DeleteMapping("/memories/{id}")
    public void deleteMemory(@PathVariable Long id) {
        memoryService.deleteMemory(id);
    }

    @GetMapping("/docs")
    public JsonNode listDocs() throws Exception {
        return aiClientService.listDocs();
    }

    @PostMapping(value = "/docs", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public JsonNode uploadDoc(@RequestParam("file") MultipartFile file) throws Exception {
        return aiClientService.uploadDoc(file.getOriginalFilename(), file.getBytes());
    }

    @DeleteMapping("/docs/{docId}")
    public Map<String, Object> deleteDoc(@PathVariable String docId) throws Exception {
        aiClientService.deleteDoc(docId);
        return Map.of("deleted", true, "id", docId);
    }

    @PostMapping("/chat")
    public ChatResponseDto chat(@Valid @RequestBody ChatRequestDto req) throws Exception {
        return chatService.chatSync(req);
    }

    @PostMapping(value = "/chat/stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public SseEmitter chatStream(
            @Valid @RequestBody ChatRequestDto req,
            @org.springframework.web.bind.annotation.RequestHeader(value = "Authorization", required = false) String authHeader) {
        SseEmitter emitter = new SseEmitter(160_000L);
        String mode = req.normalizedMode();
        AuthUtil.TokenInfo tokenInfo = AuthController.extractTokenInfo(authHeader);
        Long userId = tokenInfo != null ? tokenInfo.userId() : null;
        PreparedChat prepared = chatService.prepareUserTurn(req, userId);

        AtomicBoolean cancelled = new AtomicBoolean(false);
        AtomicReference<InputStream> upstreamRef = new AtomicReference<>();
        Runnable cancelUpstream = () -> {
            cancelled.set(true);
            InputStream in = upstreamRef.getAndSet(null);
            if (in != null) {
                try {
                    in.close();
                } catch (IOException ignored) {
                }
            }
        };
        emitter.onCompletion(cancelUpstream);
        emitter.onTimeout(cancelUpstream);
        emitter.onError(ex -> cancelUpstream.run());

        streamExecutor.submit(() -> {
            try {
                sendEvent(emitter, "meta", Map.of(
                        "type", "meta",
                        "conversationId", prepared.conversationId(),
                        "title", prepared.title(),
                        "mode", mode
                ));

                long startedAt = System.nanoTime();
                AiStreamResult result = aiClientService.streamChat(
                        prepared.contextMessages(),
                        mode,
                        req.useWeb(),
                        prepared.docIds(),
                        token -> {
                            if (!cancelled.get()) {
                                sendEventQuietly(emitter, "token", Map.of("type", "token", "content", token, "text", token), cancelUpstream);
                            }
                        },
                        sources -> {
                            if (!cancelled.get() && sources != null && !sources.isEmpty()) {
                                sendEventQuietly(emitter, "sources", Map.of("type", "sources", "sources", sources), cancelUpstream);
                            }
                        },
                        vStatus -> {
                            if (!cancelled.get() && vStatus != null) {
                                sendEventQuietly(emitter, "visual_status", vStatus, cancelUpstream);
                            }
                        },
                        vReady -> {
                            if (!cancelled.get() && vReady != null) {
                                sendEventQuietly(emitter, "visual_ready", vReady, cancelUpstream);
                            }
                        },
                        vError -> {
                            if (!cancelled.get() && vError != null) {
                                sendEventQuietly(emitter, "visual_error", vError, cancelUpstream);
                            }
                        },
                        () -> {
                            if (!cancelled.get()) {
                                sendKeepaliveQuietly(emitter, cancelUpstream);
                            }
                        },
                        cancelled,
                        upstreamRef
                );

                long totalMs = result.elapsedMs() > 0
                        ? result.elapsedMs()
                        : (System.nanoTime() - startedAt) / 1_000_000L;

                String resolvedMode = (result.intent() != null && !result.intent().isBlank())
                        ? result.intent()
                        : mode;

                if (cancelled.get()) {
                    if (result.content() != null && !result.content().isBlank()) {
                        chatService.saveAssistantMessage(
                                prepared.conversationId(),
                                result.content(),
                                totalMs,
                                resolvedMode,
                                result.visual()
                        );
                    }
                    return;
                }

                MessageDto saved = chatService.saveAssistantMessage(
                        prepared.conversationId(),
                        result.content(),
                        totalMs,
                        resolvedMode,
                        result.visual()
                );

                long promptTokens = req.message().length() / 4;
                long completionTokens = (result.content() != null ? result.content().length() : 0) / 4;
                long turnTokens = Math.max(10, promptTokens + completionTokens);
                if (userId != null) {
                    authService.recordTokenUsage(userId, turnTokens);
                }

                Map<String, Object> donePayload = new LinkedHashMap<>();
                donePayload.put("type", "done");
                donePayload.put("conversationId", prepared.conversationId());
                donePayload.put("title", prepared.title());
                donePayload.put("messageId", saved.id());
                donePayload.put("content", saved.content());
                donePayload.put("elapsedMs", totalMs);
                donePayload.put("truncated", result.truncated());
                donePayload.put("mode", resolvedMode);
                donePayload.put("toolsUsed", result.toolsUsed());
                donePayload.put("sources", result.sources());
                donePayload.put("visual", result.visual());
                donePayload.put("tokensUsed", turnTokens);
                sendEvent(emitter, "done", donePayload);
                emitter.complete();
            } catch (Exception ex) {
                if (!cancelled.get()) {
                    sendEventQuietly(emitter, "error", Map.of(
                            "type", "error",
                            "code", "GENERATION_FAILED",
                            "message", ex.getMessage() == null ? "Generation failed" : ex.getMessage()
                    ), cancelUpstream);
                    emitter.completeWithError(ex);
                }
            } finally {
                cancelUpstream.run();
            }
        });

        return emitter;
    }

    private void sendEvent(SseEmitter emitter, String eventName, Object payload) throws IOException {
        emitter.send(SseEmitter.event().name(eventName).data(objectMapper.writeValueAsString(payload)));
    }

    private void sendEventQuietly(SseEmitter emitter, String eventName, Object payload, Runnable onDisconnect) {
        try {
            sendEvent(emitter, eventName, payload);
        } catch (IOException | IllegalStateException ignored) {
            if (onDisconnect != null) {
                onDisconnect.run();
            }
        }
    }

    private void sendKeepaliveQuietly(SseEmitter emitter, Runnable onDisconnect) {
        try {
            emitter.send(SseEmitter.event().comment("keepalive"));
        } catch (IOException | IllegalStateException ignored) {
            if (onDisconnect != null) {
                onDisconnect.run();
            }
        }
    }
}

