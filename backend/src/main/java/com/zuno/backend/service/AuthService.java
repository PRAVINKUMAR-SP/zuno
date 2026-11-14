package com.zuno.backend.service;

import com.zuno.backend.dto.AuthResponseDto;
import com.zuno.backend.dto.LoginRequestDto;
import com.zuno.backend.dto.RegisterRequestDto;
import com.zuno.backend.dto.UserDto;
import com.zuno.backend.entity.User;
import com.zuno.backend.repository.UserRepository;
import com.zuno.backend.util.AuthUtil;
import java.util.List;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class AuthService {

    private static final String ADMIN_EMAIL = "pravin007ptk@gmail.com";

    private final UserRepository userRepository;

    public AuthService(UserRepository userRepository) {
        this.userRepository = userRepository;
    }

    @Transactional
    public AuthResponseDto register(RegisterRequestDto req) {
        String cleanEmail = req.email().trim().toLowerCase();
        if (userRepository.existsByEmailIgnoreCase(cleanEmail)) {
            throw new IllegalArgumentException("An account with this email already exists");
        }

        User user = new User();
        user.setName(req.name().trim());
        user.setEmail(cleanEmail);

        // Check for special Admin email rule
        if (ADMIN_EMAIL.equalsIgnoreCase(cleanEmail)) {
            user.setRole("ROLE_ADMIN");
        } else {
            user.setRole("ROLE_USER");
        }

        String salt = AuthUtil.generateSalt();
        String hash = AuthUtil.hashPassword(req.password(), salt);
        user.setSalt(salt);
        user.setPasswordHash(hash);
        user.setTotalTokensUsed(0L);
        user.setTokenLimit(-1L);

        User saved = userRepository.save(user);
        String token = AuthUtil.generateToken(saved.getId(), saved.getEmail(), saved.getRole());
        return new AuthResponseDto(token, UserDto.fromEntity(saved));
    }

    @Transactional(readOnly = true)
    public AuthResponseDto login(LoginRequestDto req) {
        String cleanEmail = req.email().trim().toLowerCase();
        User user = userRepository.findByEmailIgnoreCase(cleanEmail)
                .orElseThrow(() -> new IllegalArgumentException("Invalid email or password"));

        boolean matches = AuthUtil.verifyPassword(req.password(), user.getSalt(), user.getPasswordHash());
        if (!matches) {
            throw new IllegalArgumentException("Invalid email or password");
        }

        // If this is the admin email, ensure the role is updated to ROLE_ADMIN if not already
        if (ADMIN_EMAIL.equalsIgnoreCase(cleanEmail) && !"ROLE_ADMIN".equals(user.getRole())) {
            user.setRole("ROLE_ADMIN");
            userRepository.save(user);
        }

        String token = AuthUtil.generateToken(user.getId(), user.getEmail(), user.getRole());
        return new AuthResponseDto(token, UserDto.fromEntity(user));
    }

    @Transactional(readOnly = true)
    public UserDto getProfile(Long userId) {
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new IllegalArgumentException("User not found"));
        return UserDto.fromEntity(user);
    }

    @Transactional
    public void recordTokenUsage(Long userId, long tokens) {
        if (userId == null || tokens <= 0) return;
        userRepository.findById(userId).ifPresent(user -> {
            user.addTokens(tokens);
            userRepository.save(user);
        });
    }

    @Transactional(readOnly = true)
    public List<UserDto> listAllUsers() {
        return userRepository.findAll().stream()
                .map(UserDto::fromEntity)
                .toList();
    }

    @Transactional
    public UserDto updateUserLimit(Long targetUserId, Long newLimit) {
        User user = userRepository.findById(targetUserId)
                .orElseThrow(() -> new IllegalArgumentException("User not found"));
        user.setTokenLimit(newLimit);
        User saved = userRepository.save(user);
        return UserDto.fromEntity(saved);
    }
}

