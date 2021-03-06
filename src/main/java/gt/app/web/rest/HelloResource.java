package gt.app.web.rest;

import gt.app.config.Constants;
import gt.app.modules.email.dto.EmailDto;
import gt.app.modules.email.EmailService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.context.annotation.Profile;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

import javax.validation.Valid;
import javax.validation.constraints.NotNull;
import java.util.Map;

@RestController
@RequiredArgsConstructor
@Slf4j
@Profile({Constants.SPRING_PROFILE_DEVELOPMENT, Constants.SPRING_PROFILE_TEST})
public class HelloResource {
    private final EmailService emailService;

    @GetMapping("/debug/hello")
    public Map<String, String> sayHello() {
        return Map.of("hello", "world");
    }

    @PostMapping("/debug/sendEmail")
    public ResponseEntity<Void> sendEmailWithAttachments(@RequestBody @Valid @NotNull EmailDto email) {
        log.debug("Sending email ...");

        emailService.sendEmail(email);

        return ResponseEntity.ok().build();
    }
}
