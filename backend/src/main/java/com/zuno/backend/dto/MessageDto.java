package com.zuno.backend.dto;

import java.time.Instant;
import java.util.List;

public record MessageDto(
        Long id,
        Long conversationId,
        String role,
        String content,
        Long responseTimeMs,
        String mode,
        List<DocAttachment> attachments,
        Instant createdAt
) {}

