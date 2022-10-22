package gt.app.domain;

import lombok.Data;
import lombok.NoArgsConstructor;

import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.Id;
import java.time.Instant;
import java.util.UUID;

@Entity
@Data
@NoArgsConstructor
public class ReceivedFile {

    @Id
    UUID id;

    Instant receivedDate;
    String originalFileName;

    String storedName;

    @Enumerated(EnumType.STRING)
    FileGroup fileGroup;

    public ReceivedFile(FileGroup group, String originalFileName, String storedName) {
        this.fileGroup = group;
        this.originalFileName = originalFileName;
        this.storedName = storedName;
        this.id = UUID.randomUUID();
    }

    public enum FileGroup {
        NOTE_ATTACHMENT,
        //add other
    }
}
