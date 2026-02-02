package gt.app.modules.email.dto;

import java.util.List;

public record EmailDto(String from, List<String> to, List<String> cc, List<String> bcc,
                       String subject, String content, boolean isHtml, FileBArray[] files) {

    public static EmailDto of(String from, List<String> to, String subject, String content) {
        return new EmailDto(from, to, List.of(), List.of(), subject, content, false, new FileBArray[]{});
    }

    public record FileBArray(byte[] data, String filename) {
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
