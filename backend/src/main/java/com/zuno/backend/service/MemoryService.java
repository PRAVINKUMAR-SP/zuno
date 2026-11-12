package com.zuno.backend.service;

import com.zuno.backend.entity.UserMemory;
import com.zuno.backend.repository.UserMemoryRepository;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.stream.Collectors;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class MemoryService {

    private static final Set<String> NON_NAME_WORDS = Set.of(
            "a", "an", "the", "good", "fine", "great", "ok", "okay", "happy", "sad",
            "busy", "free", "here", "ready", "tired", "learning", "working", "trying",
            "looking", "using", "building", "creating", "studying", "asking", "not", "done"
    );

    private static final Pattern NAME_PATTERN = Pattern.compile(
            "(?i)\\b(?:my name is|i am|i'm|im|call me)\\s+([A-Za-z][A-Za-z0-9_-]{1,30})(?:\\b|[.!?,]|$)"
    );
    private static final Pattern ROLE_PATTERN = Pattern.compile(
            "(?i)\\b(?:i am|i'm|im|i work as)\\s+(?:a|an)\\s+([^.!?\n]{3,80})"
    );
    private static final Pattern LOCATION_PATTERN = Pattern.compile(
            "(?i)\\b(?:i live in|i am from|i'm from|im from)\\s+([A-Za-z][A-Za-z\\s,]{1,60})(?:[.!?\n]|$)"
    );
    private static final Pattern LEARNING_PATTERN = Pattern.compile(
            "(?i)\\b(?:i am learning|i'm learning|i know|i use|my stack is)\\s+([^.!?\n]{2,100})"
    );
    private static final Pattern REMEMBER_PATTERN = Pattern.compile(
            "(?i)^\\s*remember(?:\\s+that)?\\s*[:,-]?\\s*(.{3,200})$"
    );

    private final UserMemoryRepository memoryRepository;

    public MemoryService(UserMemoryRepository memoryRepository) {
        this.memoryRepository = memoryRepository;
    }

    @Transactional
    public void extractAndSave(String userMessage) {
        if (userMessage == null || userMessage.isBlank()) {
            return;
        }
        String text = userMessage.trim();

        Matcher rememberMatcher = REMEMBER_PATTERN.matcher(text);
        if (rememberMatcher.find()) {
            String note = rememberMatcher.group(1).trim();
            upsert("note_" + Math.abs(note.toLowerCase(Locale.ROOT).hashCode()), note);
            return;
        }

        Matcher roleMatcher = ROLE_PATTERN.matcher(text);
        if (roleMatcher.find()) {
            upsert("role", roleMatcher.group(1).trim());
        } else {
            Matcher nameMatcher = NAME_PATTERN.matcher(text);
            if (nameMatcher.find()) {
                String candidate = nameMatcher.group(1).trim();
                if (!NON_NAME_WORDS.contains(candidate.toLowerCase(Locale.ROOT))) {
                    String formatted = Character.toUpperCase(candidate.charAt(0)) + candidate.substring(1);
                    upsert("name", formatted);
                }
            }
        }

        Matcher locationMatcher = LOCATION_PATTERN.matcher(text);
        if (locationMatcher.find()) {
            upsert("location", locationMatcher.group(1).trim());
        }

        Matcher learningMatcher = LEARNING_PATTERN.matcher(text);
        if (learningMatcher.find()) {
            String val = learningMatcher.group(1).trim();
            if (val.length() >= 2) {
                upsert("skills_or_interests", val);
            }
        }
    }

    @Transactional(readOnly = true)
    public List<UserMemory> listMemories() {
        return memoryRepository.findAllByOrderByUpdatedAtDesc();
    }

    @Transactional
    public void deleteMemory(Long id) {
        memoryRepository.deleteById(id);
    }

    @Transactional(readOnly = true)
    public String buildMemoryPrompt() {
        List<UserMemory> memories = memoryRepository.findAllByOrderByUpdatedAtDesc();
        if (memories.isEmpty()) {
            return "";
        }
        String facts = memories.stream()
                .map(m -> formatFact(m.getMemoryKey(), m.getMemoryValue()))
                .collect(Collectors.joining(" "));
        return "Known user facts: " + facts
                + " Only mention these when relevant or asked about the user; never invent extra personal details.";
    }

    private String formatFact(String key, String value) {
        return switch (key) {
            case "name" -> "The user's name is " + value + ".";
            case "role" -> "The user works as a " + value + ".";
            case "location" -> "The user is from/lives in " + value + ".";
            case "skills_or_interests" -> "The user knows or is learning " + value + ".";
            default -> value.endsWith(".") ? value : value + ".";
        };
    }

    private void upsert(String key, String value) {
        UserMemory memory = memoryRepository.findByMemoryKey(key).orElseGet(UserMemory::new);
        memory.setMemoryKey(key);
        memory.setMemoryValue(value);
        memoryRepository.save(memory);
    }
}

