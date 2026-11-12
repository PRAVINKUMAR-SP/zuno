package com.zuno.backend.service;

import com.zuno.backend.dto.ChatRequestDto;
import com.zuno.backend.dto.ChatResponseDto;
import com.zuno.backend.dto.ConversationDto;
import com.zuno.backend.dto.DocAttachment;
import com.zuno.backend.dto.MessageDto;
import com.zuno.backend.entity.ChatMessage;
import com.zuno.backend.entity.Conversation;
import com.zuno.backend.repository.ChatMessageRepository;
import com.zuno.backend.repository.ConversationRepository;
import com.zuno.backend.service.AiClientService.AiMessage;
import com.zuno.backend.service.AiClientService.AiStreamResult;
import java.time.Instant;
import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.ObjectMapper;

@Service
public class ChatService {

    private static final int MAX_CONTEXT_MESSAGES = 10;

    private final ConversationRepository conversationRepository;
    private final ChatMessageRepository chatMessageRepository;
    private final AiClientService aiClientService;
    private final MemoryService memoryService;
    private final ObjectMapper objectMapper;

    public record PreparedChat(
            Long conversationId,
            String title,
            List<AiMessage> contextMessages,
            List<String> docIds) {}

    public ChatService(
            ConversationRepository conversationRepository,
            ChatMessageRepository chatMessageRepository,
            AiClientService aiClientService,
            MemoryService memoryService,
            ObjectMapper objectMapper) {
        this.conversationRepository = conversationRepository;
        this.chatMessageRepository = chatMessageRepository;
        this.aiClientService = aiClientService;
        this.memoryService = memoryService;
        this.objectMapper = objectMapper;
    }

    @Transactional(readOnly = true)
    public List<ConversationDto> listConversations() {
        return conversationRepository.findAllByOrderByUpdatedAtDesc().stream()
                .map(this::toDto)
                .toList();
    }

    @Transactional
    public ConversationDto createConversation(String title) {
        Conversation conv = new Conversation();
        conv.setTitle((title == null || title.isBlank()) ? "New Chat" : title.trim());
        return toDto(conversationRepository.save(conv));
    }

    @Transactional
    public ConversationDto renameConversation(Long id, String title) {
        Conversation conv = findConversation(id);
        conv.setTitle(title.trim());
        return toDto(conversationRepository.save(conv));
    }

    @Transactional
    public void deleteConversation(Long id) {
        Conversation conv = findConversation(id);
        conversationRepository.delete(conv);
    }

    @Transactional(readOnly = true)
    public List<MessageDto> getMessages(Long conversationId) {
        findConversation(conversationId);
        return chatMessageRepository.findByConversationIdOrderByCreatedAtAscIdAsc(conversationId).stream()
                .map(this::toDto)
                .toList();
    }

    @Transactional
    public PreparedChat prepareUserTurn(ChatRequestDto req) {
        Conversation conv = req.conversationId() != null
                ? conversationRepository.findById(req.conversationId()).orElse(null)
                : null;
        if (conv == null) {
            conv = new Conversation();
            conv.setTitle(deriveTitle(req.message()));
            conv = conversationRepository.save(conv);
        }

        if ("New Chat".equals(conv.getTitle())) {
            conv.setTitle(deriveTitle(req.message()));
        }

        ChatMessage userMessage = new ChatMessage();
        userMessage.setConversation(conv);
        userMessage.setRole("user");
        userMessage.setContent(req.message().trim());
        userMessage.setMode(req.normalizedMode());
        if (req.attachments() != null && !req.attachments().isEmpty()) {
            try {
                userMessage.setAttachmentsJson(objectMapper.writeValueAsString(req.attachments()));
            } catch (Exception ignored) {
            }
        }
        chatMessageRepository.save(userMessage);

        memoryService.extractAndSave(req.message());

        conv.setUpdatedAt(Instant.now());
        conversationRepository.save(conv);

        List<ChatMessage> allMessages =
                chatMessageRepository.findByConversationIdOrderByCreatedAtAscIdAsc(conv.getId());
        Set<String> docIdSet = new LinkedHashSet<>();
        for (ChatMessage m : allMessages) {
            for (DocAttachment att : parseAttachments(m.getAttachmentsJson())) {
                if (att.id() != null && !att.id().isBlank()) {
                    docIdSet.add(att.id());
                }
            }
        }
        int startIdx = Math.max(0, allMessages.size() - MAX_CONTEXT_MESSAGES);
        List<AiMessage> context = new ArrayList<>();
        String memoryPrompt = memoryService.buildMemoryPrompt();
        if (!memoryPrompt.isBlank()) {
            context.add(new AiMessage("system", memoryPrompt));
        }
        if (startIdx > 0) {
            List<String> earlierTopics = new ArrayList<>();
            for (int i = 0; i < startIdx && earlierTopics.size() < 4; i++) {
                ChatMessage earlier = allMessages.get(i);
                if ("user".equals(earlier.getRole()) && earlier.getContent() != null) {
                    String snippet = earlier.getContent().replaceAll("\\s+", " ").trim();
                    if (!snippet.isBlank()) {
                        earlierTopics.add(snippet.length() > 80 ? snippet.substring(0, 77) + "..." : snippet);
                    }
                }
            }
            if (!earlierTopics.isEmpty()) {
                context.add(new AiMessage("system", "Earlier topics in this chat: " + String.join(" | ", earlierTopics)));
            }
        }
        for (int i = startIdx; i < allMessages.size(); i++) {
            ChatMessage m = allMessages.get(i);
            context.add(new AiMessage(m.getRole(), m.getContent()));
        }

        return new PreparedChat(conv.getId(), conv.getTitle(), context, new ArrayList<>(docIdSet));
    }

    @Transactional
    public MessageDto saveAssistantMessage(Long conversationId, String content, long elapsedMs, String mode) {
        Conversation conv = findConversation(conversationId);
        String safeContent = (content == null || content.isBlank())
                ? "I could not generate a response. Please try again."
                : content.trim();

        ChatMessage assistantMessage = new ChatMessage();
        assistantMessage.setConversation(conv);
        assistantMessage.setRole("assistant");
        assistantMessage.setContent(safeContent);
        assistantMessage.setResponseTimeMs(elapsedMs);
        assistantMessage.setMode(mode);
        ChatMessage saved = chatMessageRepository.save(assistantMessage);

        conv.setUpdatedAt(Instant.now());
        conversationRepository.save(conv);

        return toDto(saved);
    }

    public ChatResponseDto chatSync(ChatRequestDto req) throws Exception {
        String mode = req.normalizedMode();
        PreparedChat prepared = prepareUserTurn(req);
        AiStreamResult result = aiClientService.chatSync(
                prepared.contextMessages(), mode, req.useWeb(), prepared.docIds());
        String resolvedMode = (result.intent() != null && !result.intent().isBlank()) ? result.intent() : mode;
        MessageDto saved = saveAssistantMessage(
                prepared.conversationId(), result.content(), result.elapsedMs(), resolvedMode);
        return new ChatResponseDto(
                prepared.conversationId(),
                prepared.title(),
                saved.id(),
                saved.content(),
                result.elapsedMs(),
                result.truncated(),
                resolvedMode
        );
    }

    private Conversation findConversation(Long id) {
        return conversationRepository.findById(id)
                .orElseThrow(() -> new ResponseStatusException(
                        HttpStatus.NOT_FOUND, "Conversation not found: " + id));
    }

    private String deriveTitle(String message) {
        String clean = message.replaceAll("\\s+", " ").trim();
        if (clean.length() <= 52) {
            return clean;
        }
        return clean.substring(0, 49) + "...";
    }

    private ConversationDto toDto(Conversation c) {
        return new ConversationDto(c.getId(), c.getTitle(), c.getCreatedAt(), c.getUpdatedAt());
    }

    private List<DocAttachment> parseAttachments(String json) {
        if (json == null || json.isBlank()) {
            return List.of();
        }
        try {
            JsonNode arr = objectMapper.readTree(json);
            if (!arr.isArray()) {
                return List.of();
            }
            List<DocAttachment> list = new ArrayList<>();
            for (JsonNode item : arr) {
                String id = item.path("id").asString("");
                String name = item.path("name").asString("");
                if (!name.isBlank()) {
                    list.add(new DocAttachment(id, name));
                }
            }
            return list;
        } catch (Exception ex) {
            return List.of();
        }
    }

    private MessageDto toDto(ChatMessage m) {
        return new MessageDto(
                m.getId(),
                m.getConversation().getId(),
                m.getRole(),
                m.getContent(),
                m.getResponseTimeMs(),
                m.getMode(),
                parseAttachments(m.getAttachmentsJson()),
                m.getCreatedAt()
        );
    }
}

