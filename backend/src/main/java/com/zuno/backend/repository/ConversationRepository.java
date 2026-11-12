package com.zuno.backend.repository;

import com.zuno.backend.entity.Conversation;
import java.util.List;
import org.springframework.data.jpa.repository.JpaRepository;

public interface ConversationRepository extends JpaRepository<Conversation, Long> {
    List<Conversation> findAllByOrderByUpdatedAtDesc();
}

