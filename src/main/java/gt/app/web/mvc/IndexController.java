package gt.app.web.mvc;

import gt.app.config.security.AppUserDetails;
import gt.app.domain.Note;
import gt.app.modules.note.NoteService;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Pageable;
import org.springframework.data.domain.Sort;
import org.springframework.data.web.PageableDefault;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.GetMapping;

@Controller
@RequiredArgsConstructor
public class IndexController {

    private final NoteService noteService;

    @GetMapping({"/", ""})
    public String index(Model model,
                        @PageableDefault(size = 10, sort = "createdDate", direction = Sort.Direction.DESC) Pageable pageable) {
        model.addAttribute("notes", noteService.readAll(pageable));
        model.addAttribute("note", new Note());
        return "landing";
    }

    @GetMapping("/admin")
    public String adminHome(Model model, @AuthenticationPrincipal AppUserDetails principal) {
        model.addAttribute("message", getWelcomeMessage(principal));
        return "admin";
    }

    @GetMapping("/note")
    public String userHome(Model model,
                           @AuthenticationPrincipal AppUserDetails principal,
                           @PageableDefault(size = 10, sort = "createdDate", direction = Sort.Direction.DESC) Pageable pageable) {
        model.addAttribute("message", getWelcomeMessage(principal));
        model.addAttribute("notes", noteService.readAllByUser(pageable, principal.getId()));
        model.addAttribute("note", new Note());
        return "note";
    }

    private String getWelcomeMessage(AppUserDetails principal) {
        return "Hello " + principal.getUsername() + "!";
    }

}
