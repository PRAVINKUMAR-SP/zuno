package com.zuno.backend.dto;

import java.time.Instant;
import java.util.List;
import java.util.Map;

public record MessageDto(
        Long id,
        Long conversationId,
        String role,
        String content,
        Long responseTimeMs,
        String mode,
        List<DocAttachment> attachments,
        Map<String, Object> visual,
        Instant createdAt
) {}

