package com.zuno.backend.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

public record RenameConversationDto(
        @NotBlank(message = "Title cannot be empty")
        @Size(max = 200, message = "Title too long")
        String title
) {}

