package gt.app.modules.note;

import lombok.Data;
import org.springframework.web.multipart.MultipartFile;

import jakarta.validation.constraints.NotNull;

@Data
public class NoteCreateDto {

    @NotNull
    MultipartFile[] files;
    private String title;
    private String content;
}
