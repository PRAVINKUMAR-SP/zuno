package com.zuno.backend.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import java.util.List;

public record ChatRequestDto(
        Long conversationId,
        @NotBlank(message = "Message cannot be empty")
        @Size(max = 8000, message = "Message is too long")
        String message,
        String mode,
        Boolean useWeb,
        List<DocAttachment> attachments
) {
    public String normalizedMode() {
        if ("fast".equalsIgnoreCase(mode)) {
            return "fast";
        }
        if ("detailed".equalsIgnoreCase(mode)) {
            return "detailed";
        }
        return "auto";
    }
}

