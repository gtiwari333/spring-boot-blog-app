package gt.app.web.rest;

import gt.app.config.Constants;
import gt.app.modules.email.dto.EmailDto;
import gt.app.modules.email.EmailService;
import gt.app.modules.note.NoteService;
import gt.app.modules.note.dto.NoteReadDto;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.context.annotation.Profile;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.domain.Sort;
import org.springframework.data.web.PageableDefault;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotNull;

import java.util.Map;

@RestController
@RequiredArgsConstructor
@Slf4j
@Profile({Constants.SPRING_PROFILE_DEVELOPMENT, Constants.SPRING_PROFILE_TEST})
@RequestMapping("/debug")
public class HelloResource {
    private final EmailService emailService;
    private final NoteService noteService;

    @GetMapping("/hello")
    public Map<String, String> sayHello() {
        return Map.of("hello", "world");
    }

    @PostMapping("/sendEmail")
    public ResponseEntity<Void> sendEmailWithAttachments(@RequestBody @Valid @NotNull EmailDto email) {
        log.debug("Sending email ...");

        emailService.sendEmail(email);

        return ResponseEntity.ok().build();
    }

    @GetMapping("/notes")
    public Page<NoteReadDto> index(@PageableDefault(size = 10, sort = "createdDate", direction = Sort.Direction.DESC) Pageable pageable) {
        return noteService.readAll(pageable);
    }

}
