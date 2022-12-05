package gt.app.modules.note.dto;

import java.time.Instant;
import java.util.List;
import java.util.UUID;

public record NoteReadDto(Long id, String title, String content, Long userId, String username, Instant createdDate,
                          List<FileInfo> files) {

    ////required for GraalVMNativeImage::
    //SpelEvaluationException: EL1004E: Method call: Method size() cannot be found on type java.util.ArrayList
    //Caused by: org.thymeleaf.exceptions.TemplateProcessingException: Exception evaluating SpringEL expression: "note.files.size()>0" (template: "note/_notes" - line 43, col 18)
    public int getFileSize() {
        if (files == null) {
            return 0;
        }
        return files.size();
    }

    public record FileInfo(UUID id, String name) {
    }
}
