package gt.app.modules.note.dto;

import io.vertx.ext.web.FileUpload;

import jakarta.validation.constraints.NotNull;

public record NoteCreateDto(@NotNull FileUpload[] files, String title, String content) {
}
