package gt.app.modules.note.dto;

import java.time.Instant;
import java.util.List;
import java.util.UUID;

public record NoteReadDto(Long id, String title, String content, Long userId, String username, Instant createdDate,
                          List<FileInfo> files) {
    public record FileInfo(UUID id, String name) {
    }
}
