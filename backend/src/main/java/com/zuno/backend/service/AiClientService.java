package com.zuno.backend.service;

import java.io.BufferedReader;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicReference;
import java.util.function.Consumer;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.ObjectMapper;

@Service
public class AiClientService {

    private final HttpClient httpClient;
    private final ObjectMapper objectMapper;
    private final String baseUrl;
    private final int timeoutSeconds;

    public record AiMessage(String role, String content) {}

    public record AiStreamResult(
            String content,
            long elapsedMs,
            boolean truncated,
            String intent,
            List<String> toolsUsed,
            List<Map<String, String>> sources) {}

    public AiClientService(
            ObjectMapper objectMapper,
            @Value("${zuno.ai.base-url:http://127.0.0.1:8001}") String baseUrl,
            @Value("${zuno.ai.timeout-seconds:150}") int timeoutSeconds) {
        this.objectMapper = objectMapper;
        this.baseUrl = baseUrl.endsWith("/") ? baseUrl.substring(0, baseUrl.length() - 1) : baseUrl;
        this.timeoutSeconds = timeoutSeconds;
        this.httpClient = HttpClient.newBuilder()
                .version(HttpClient.Version.HTTP_1_1)
                .connectTimeout(Duration.ofSeconds(3))
                .build();
    }

    public JsonNode checkHealth() {
        try {
            HttpRequest request = HttpRequest.newBuilder()
                    .uri(URI.create(baseUrl + "/health"))
                    .timeout(Duration.ofSeconds(3))
                    .GET()
                    .build();
            HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
            if (response.statusCode() == 200) {
                return objectMapper.readTree(response.body());
            }
            return objectMapper.createObjectNode().put("status", "error").put("ready", false);
        } catch (Exception ex) {
            return objectMapper.createObjectNode()
                    .put("status", "offline")
                    .put("ready", false)
                    .put("error", ex.getMessage() == null ? "unreachable" : ex.getMessage());
        }
    }

    private String buildChatPayload(
            List<AiMessage> messages,
            String mode,
            Boolean useWeb,
            List<String> docIds) throws Exception {
        Map<String, Object> body = new HashMap<>();
        body.put("messages", messages);
        body.put("mode", mode);
        if (useWeb != null) {
            body.put("use_web", useWeb);
        }
        if (docIds != null) {
            body.put("doc_ids", docIds);
        }
        return objectMapper.writeValueAsString(body);
    }

    private List<String> parseStringList(JsonNode node) {
        List<String> list = new ArrayList<>();
        if (node != null && node.isArray()) {
            for (JsonNode item : node) {
                String v = item.asString("");
                if (!v.isBlank()) {
                    list.add(v);
                }
            }
        }
        return list;
    }

    private List<Map<String, String>> parseSources(JsonNode node) {
        List<Map<String, String>> list = new ArrayList<>();
        if (node != null && node.isArray()) {
            for (JsonNode item : node) {
                Map<String, String> entry = new HashMap<>();
                entry.put("kind", item.path("kind").asString(""));
                entry.put("title", item.path("title").asString(""));
                String url = item.path("url").asString("");
                if (!url.isBlank()) {
                    entry.put("url", url);
                }
                list.add(entry);
            }
        }
        return list;
    }

    public AiStreamResult streamChat(
            List<AiMessage> messages,
            String mode,
            Boolean useWeb,
            List<String> docIds,
            Consumer<String> onToken,
            Runnable onKeepalive,
            AtomicBoolean cancelled,
            AtomicReference<InputStream> upstreamRef) throws Exception {
        return streamChat(messages, mode, useWeb, docIds, onToken, null, onKeepalive, cancelled, upstreamRef);
    }

    public AiStreamResult streamChat(
            List<AiMessage> messages,
            String mode,
            Boolean useWeb,
            List<String> docIds,
            Consumer<String> onToken,
            Consumer<List<Map<String, String>>> onSources,
            Runnable onKeepalive,
            AtomicBoolean cancelled,
            AtomicReference<InputStream> upstreamRef) throws Exception {
        String payload = buildChatPayload(messages, mode, useWeb, docIds);

        HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create(baseUrl + "/v1/chat/stream"))
                .timeout(Duration.ofSeconds(timeoutSeconds))
                .header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(payload, StandardCharsets.UTF_8))
                .build();

        HttpResponse<InputStream> response =
                httpClient.send(request, HttpResponse.BodyHandlers.ofInputStream());

        if (response.statusCode() != 200) {
            String errBody = new String(response.body().readAllBytes(), StandardCharsets.UTF_8);
            throw new IllegalStateException("AI service returned HTTP " + response.statusCode() + ": " + errBody);
        }

        InputStream bodyStream = response.body();
        upstreamRef.set(bodyStream);
        if (cancelled.get()) {
            bodyStream.close();
            return new AiStreamResult("", 0, false, mode, List.of(), List.of());
        }

        StringBuilder fullContent = new StringBuilder();
        long elapsedMs = 0;
        boolean truncated = false;
        String resolvedIntent = mode;
        List<String> toolsUsed = List.of();
        List<Map<String, String>> sources = List.of();
        boolean receivedDone = false;

        try (BufferedReader reader = new BufferedReader(
                new InputStreamReader(bodyStream, StandardCharsets.UTF_8))) {
            String line;
            while (!cancelled.get() && (line = reader.readLine()) != null) {
                if (line.startsWith(":")) {
                    if (onKeepalive != null) {
                        onKeepalive.run();
                    }
                    continue;
                }
                if (!line.startsWith("data:")) {
                    continue;
                }
                String jsonPart = line.substring(5).trim();
                if (jsonPart.isEmpty()) {
                    continue;
                }
                JsonNode event = objectMapper.readTree(jsonPart);
                String type = event.path("type").asString("");
                switch (type) {
                    case "sources" -> {
                        List<Map<String, String>> earlySources = parseSources(event.path("sources"));
                        if (!earlySources.isEmpty()) {
                            sources = earlySources;
                            if (onSources != null) {
                                onSources.accept(earlySources);
                            }
                        }
                    }
                    case "token" -> {
                        String delta = event.path("content").asString("");
                        if (delta.isEmpty()) {
                            delta = event.path("text").asString("");
                        }
                        if (!delta.isEmpty()) {
                            fullContent.append(delta);
                            onToken.accept(delta);
                        }
                    }
                    case "done" -> {
                        receivedDone = true;
                        String finalText = event.path("content").asString("");
                        if (!finalText.isEmpty()) {
                            fullContent.setLength(0);
                            fullContent.append(finalText);
                        }
                        elapsedMs = event.path("elapsedMs").asLong(0L);
                        truncated = event.path("truncated").asBoolean(false);
                        String intentVal = event.path("intent").asString("");
                        if (!intentVal.isBlank()) {
                            resolvedIntent = intentVal;
                        }
                        toolsUsed = parseStringList(event.path("toolsUsed"));
                        List<Map<String, String>> doneSources = parseSources(event.path("sources"));
                        if (!doneSources.isEmpty()) {
                            sources = doneSources;
                        }
                    }
                    case "error" -> throw new IllegalStateException(
                            event.path("message").asString("Unknown AI error"));
                    default -> {
                    }
                }
            }
        } catch (java.io.IOException ex) {
            if (!cancelled.get()) {
                throw ex;
            }
        }

        if (!cancelled.get() && !receivedDone) {
            System.err.println("[AiClientService] Upstream stream ended before done event (mode="
                    + mode + ", chars=" + fullContent.length() + ")");
        }

        return new AiStreamResult(fullContent.toString(), elapsedMs, truncated, resolvedIntent, toolsUsed, sources);
    }

    public AiStreamResult chatSync(List<AiMessage> messages, String mode, Boolean useWeb, List<String> docIds) throws Exception {
        String payload = buildChatPayload(messages, mode, useWeb, docIds);

        HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create(baseUrl + "/v1/chat"))
                .timeout(Duration.ofSeconds(timeoutSeconds))
                .header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(payload, StandardCharsets.UTF_8))
                .build();

        HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
        if (response.statusCode() != 200) {
            throw new IllegalStateException("AI service returned HTTP " + response.statusCode() + ": " + response.body());
        }
        JsonNode root = objectMapper.readTree(response.body());
        String intentVal = root.path("intent").asString("");
        return new AiStreamResult(
                root.path("content").asString(""),
                root.path("elapsedMs").asLong(0L),
                root.path("truncated").asBoolean(false),
                intentVal.isBlank() ? mode : intentVal,
                parseStringList(root.path("toolsUsed")),
                parseSources(root.path("sources"))
        );
    }

    public JsonNode listDocs() throws Exception {
        HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create(baseUrl + "/v1/docs"))
                .timeout(Duration.ofSeconds(10))
                .GET()
                .build();
        HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
        if (response.statusCode() != 200) {
            throw new IllegalStateException("AI service returned HTTP " + response.statusCode());
        }
        return objectMapper.readTree(response.body());
    }

    public JsonNode uploadDoc(String filename, byte[] fileBytes) throws Exception {
        String boundary = "----ZunoDocBoundary" + UUID.randomUUID().toString().replace("-", "");
        String safeName = (filename == null || filename.isBlank()) ? "document.txt" : filename.replace("\"", "");
        ByteArrayOutputStream baos = new ByteArrayOutputStream();
        baos.write(("--" + boundary + "\r\n").getBytes(StandardCharsets.UTF_8));
        baos.write(("Content-Disposition: form-data; name=\"file\"; filename=\"" + safeName + "\"\r\n").getBytes(StandardCharsets.UTF_8));
        baos.write("Content-Type: application/octet-stream\r\n\r\n".getBytes(StandardCharsets.UTF_8));
        baos.write(fileBytes);
        baos.write(("\r\n--" + boundary + "--\r\n").getBytes(StandardCharsets.UTF_8));

        HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create(baseUrl + "/v1/docs"))
                .timeout(Duration.ofSeconds(30))
                .header("Content-Type", "multipart/form-data; boundary=" + boundary)
                .POST(HttpRequest.BodyPublishers.ofByteArray(baos.toByteArray()))
                .build();
        HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
        if (response.statusCode() != 200) {
            throw new IllegalStateException(response.body());
        }
        return objectMapper.readTree(response.body());
    }

    public void deleteDoc(String docId) throws Exception {
        HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create(baseUrl + "/v1/docs/" + docId))
                .timeout(Duration.ofSeconds(10))
                .DELETE()
                .build();
        HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
        if (response.statusCode() != 200 && response.statusCode() != 404) {
            throw new IllegalStateException("Delete doc failed: HTTP " + response.statusCode());
        }
    }
}

