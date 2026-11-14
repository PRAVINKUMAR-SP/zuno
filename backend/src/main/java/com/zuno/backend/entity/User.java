package com.zuno.backend.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.PrePersist;
import jakarta.persistence.PreUpdate;
import jakarta.persistence.Table;
import java.time.Instant;

@Entity
@Table(name = "users")
public class User {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, length = 100)
    private String name;

    @Column(nullable = false, unique = true, length = 150)
    private String email;

    @Column(name = "password_hash", nullable = false, length = 255)
    private String passwordHash;

    @Column(nullable = false, length = 100)
    private String salt;

    @Column(nullable = false, length = 50)
    private String role = "ROLE_USER";

    @Column(name = "total_tokens_used", nullable = false)
    private Long totalTokensUsed = 0L;

    @Column(name = "token_limit", nullable = false)
    private Long tokenLimit = -1L; // -1 means unlimited

    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt;

    @Column(name = "updated_at", nullable = false)
    private Instant updatedAt;

    @PrePersist
    protected void onCreate() {
        Instant now = Instant.now();
        this.createdAt = now;
        this.updatedAt = now;
        if (this.totalTokensUsed == null) {
            this.totalTokensUsed = 0L;
        }
        if (this.tokenLimit == null) {
            this.tokenLimit = -1L;
        }
    }

    @PreUpdate
    protected void onUpdate() {
        this.updatedAt = Instant.now();
    }

    public Long getId() {
        return id;
    }

    public String getName() {
        return name;
    }

    public void setName(String name) {
        this.name = name;
    }

    public String getEmail() {
        return email;
    }

    public void setEmail(String email) {
        this.email = email;
    }

    public String getPasswordHash() {
        return passwordHash;
    }

    public void setPasswordHash(String passwordHash) {
        this.passwordHash = passwordHash;
    }

    public String getSalt() {
        return salt;
    }

    public void setSalt(String salt) {
        this.salt = salt;
    }

    public String getRole() {
        return role;
    }

    public void setRole(String role) {
        this.role = role;
    }

    public Long getTotalTokensUsed() {
        return totalTokensUsed != null ? totalTokensUsed : 0L;
    }

    public void setTotalTokensUsed(Long totalTokensUsed) {
        this.totalTokensUsed = totalTokensUsed;
    }

    public void addTokens(long tokens) {
        if (tokens > 0) {
            this.totalTokensUsed = getTotalTokensUsed() + tokens;
        }
    }

    public Long getTokenLimit() {
        return tokenLimit != null ? tokenLimit : -1L;
    }

    public void setTokenLimit(Long tokenLimit) {
        this.tokenLimit = tokenLimit;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }

    public Instant getUpdatedAt() {
        return updatedAt;
    }
}

