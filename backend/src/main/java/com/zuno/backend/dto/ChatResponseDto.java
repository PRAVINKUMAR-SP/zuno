package com.zuno.backend.dto;

public record ChatResponseDto(
        Long conversationId,
        String title,
        Long messageId,
        String content,
        Long elapsedMs,
        boolean truncated,
        String mode
) {}

