package com.zuno.backend.controller;

import com.zuno.backend.dto.UserDto;
import com.zuno.backend.service.AuthService;
import com.zuno.backend.util.AuthUtil;
import java.util.List;
import java.util.Map;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/admin")
public class AdminController {

    private final AuthService authService;

    public AdminController(AuthService authService) {
        this.authService = authService;
    }

    private boolean isAdmin(String authHeader) {
        AuthUtil.TokenInfo info = AuthController.extractTokenInfo(authHeader);
        return info != null && "ROLE_ADMIN".equals(info.role());
    }

    @GetMapping("/users")
    public ResponseEntity<?> listUsers(@RequestHeader(value = "Authorization", required = false) String authHeader) {
        if (!isAdmin(authHeader)) {
            return ResponseEntity.status(HttpStatus.FORBIDDEN).body(Map.of("error", "Admin access required"));
        }
        List<UserDto> users = authService.listAllUsers();
        return ResponseEntity.ok(users);
    }

    @PatchMapping("/users/{id}/limit")
    public ResponseEntity<?> updateUserLimit(
            @PathVariable Long id,
            @RequestBody Map<String, Object> body,
            @RequestHeader(value = "Authorization", required = false) String authHeader) {
        if (!isAdmin(authHeader)) {
            return ResponseEntity.status(HttpStatus.FORBIDDEN).body(Map.of("error", "Admin access required"));
        }
        Number limitNum = (Number) body.get("tokenLimit");
        if (limitNum == null) {
            return ResponseEntity.badRequest().body(Map.of("error", "tokenLimit is required"));
        }
        try {
            UserDto updated = authService.updateUserLimit(id, limitNum.longValue());
            return ResponseEntity.ok(updated);
        } catch (Exception ex) {
            return ResponseEntity.badRequest().body(Map.of("error", ex.getMessage()));
        }
    }
}

