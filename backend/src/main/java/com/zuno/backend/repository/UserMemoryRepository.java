package com.zuno.backend.repository;

import com.zuno.backend.entity.UserMemory;
import java.util.List;
import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;

public interface UserMemoryRepository extends JpaRepository<UserMemory, Long> {
    Optional<UserMemory> findByMemoryKey(String memoryKey);
    List<UserMemory> findAllByOrderByUpdatedAtDesc();
}

