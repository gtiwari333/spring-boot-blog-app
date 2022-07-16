package gt.app.web.rest;

import gt.app.config.security.SecurityUtils;
import lombok.RequiredArgsConstructor;
import org.springframework.security.core.userdetails.User;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api")
@RequiredArgsConstructor
public class UserResource {

    @GetMapping("/account")
    public User getAccount() {
        return SecurityUtils.getCurrentUserDetails();
    }
}
