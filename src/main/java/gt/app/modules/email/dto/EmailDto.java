package gt.app.modules.email.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.Collection;
import java.util.HashSet;

@Data
@Builder
public class EmailDto {

    String from;
    Collection<String> to;
    Collection<String> cc;
    Collection<String> bcc;
    String subject;
    String content;
    boolean isHtml;
    FileBArray[] files;

    @Data
    @AllArgsConstructor
    @NoArgsConstructor
    public static class FileBArray {
        byte[] data;
        String filename;
    }

    @Override
    public String toString() {
        return "EmailDto{" +
            "from='" + from + '\'' +
            ", to=" + to +
            ", cc=" + cc +
            ", bcc=" + bcc +
            ", subject='" + subject + '\'' +
            '}';
    }
}
