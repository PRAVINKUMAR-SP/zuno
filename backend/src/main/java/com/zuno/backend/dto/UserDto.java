package com.zuno.backend.dto;

import com.zuno.backend.entity.User;
import java.time.Instant;

public record UserDto(
        Long id,
        String name,
        String email,
        String role,
        Long totalTokensUsed,
        Long tokenLimit,
        Instant createdAt
) {
    public static UserDto fromEntity(User user) {
        if (user == null) return null;
        return new UserDto(
                user.getId(),
                user.getName(),
                user.getEmail(),
                user.getRole(),
                user.getTotalTokensUsed(),
                user.getTokenLimit(),
                user.getCreatedAt()
        );
    }
}

