package gt.app.modules.email;

import gt.app.modules.email.dto.EmailDto;
import io.quarkus.mailer.Mail;
import io.quarkus.mailer.Mailer;
import jakarta.enterprise.context.ApplicationScoped;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;

@ApplicationScoped
@Slf4j
@RequiredArgsConstructor
public class EmailService {

    private final Mailer mailer; // Quarkus Mailer replaces JavaMailSender

    public void sendEmail(EmailDto email) {

        try {
            Mail m = new Mail()
                .setFrom(email.from())
                .setSubject(email.subject())
                .setTo(email.to())
                .setCc(email.cc())
                .setBcc(email.bcc());

            if (email.isHtml()) {
                m.setHtml(email.content());
            } else {
                m.setText(email.content());
            }

            if (email.files() != null) {
                for (var file : email.files()) {
                    // Quarkus handles ByteArray to attachment mapping internally
                    m.addAttachment(file.filename(), file.data(), "application/octet-stream");
                }
            }

            mailer.send(m);

            log.debug("Email Sent subject: {}", email.subject());
        } catch (Exception e) {
            log.error("Failed to send email", e);
        }
    }
}
