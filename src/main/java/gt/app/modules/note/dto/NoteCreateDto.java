package gt.app.modules.note.dto;

import org.springframework.web.multipart.MultipartFile;

import jakarta.validation.constraints.NotNull;

public record NoteCreateDto(@NotNull MultipartFile[] files, String title, String content) {
}
