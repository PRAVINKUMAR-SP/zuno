package com.zuno.backend.dto;

public record AuthResponseDto(
        String token,
        UserDto user
) {}

