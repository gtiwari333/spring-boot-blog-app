package gt.app.modules.user;

import gt.app.config.Constants;
import gt.app.config.security.AppUserDetails;
import gt.app.domain.AppUser;
import gt.app.domain.LiteUser;
import gt.app.exception.RecordNotFoundException;
import gt.app.modules.email.EmailService;
import gt.app.modules.email.dto.EmailDto;
import gt.app.modules.user.dto.PasswordUpdateDTO;
import gt.app.modules.user.dto.UserProfileUpdateDTO;
import gt.app.modules.user.dto.UserSignUpDTO;
import lombok.RequiredArgsConstructor;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.Set;

@Service
@Transactional
@RequiredArgsConstructor
public class UserService {

    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;
    private final AuthorityService authorityService;
    private final EmailService emailService;

    private final LiteUserRepository liteUserRepository;

    public void update(UserProfileUpdateDTO toUpdate, AppUserDetails userDetails) {
        LiteUser user = liteUserRepository.findOneByUniqueId(userDetails.getUsername())
            .orElseThrow(() -> new RecordNotFoundException("User", "login", userDetails.getUsername()));

        user.setFirstName(toUpdate.getFirstName());
        user.setLastName(toUpdate.getLastName());
        user.setEmail(toUpdate.getEmail());

        liteUserRepository.save(user);
    }

    public void updatePassword(PasswordUpdateDTO toUpdate, AppUserDetails userDetails) {
        LiteUser user = liteUserRepository.findOneByUniqueId(userDetails.getUsername())
            .orElseThrow(() -> new RecordNotFoundException("User", "login", userDetails.getUsername()));

        user.setPassword(passwordEncoder.encode(toUpdate.pwdPlainText()));
        liteUserRepository.save(user);
    }

    public AppUser create(UserSignUpDTO toCreate) {

        var user = new AppUser(toCreate.getUniqueId(), toCreate.getFirstName(), toCreate.getLastName(), toCreate.getEmail());

        user.setPassword(passwordEncoder.encode(toCreate.getPwdPlaintext()));

        user.setAuthorities(authorityService.findByNameIn(Constants.ROLE_USER));

        userRepository.save(user);

        EmailDto dto = EmailDto.of("system@noteapp", Set.of(user.getEmail()),
            "NoteApp Account Created!",
            "Thanks for signing up.");

        emailService.sendEmail(dto);

        return user;
    }

    public void delete(Long id) {
        LiteUser author = liteUserRepository.findByIdAndActiveIsTrue(id)
            .orElseThrow(() -> new RecordNotFoundException("User", "id", id));

        author.setActive(Boolean.FALSE);
        liteUserRepository.save(author);
    }

    public AppUser save(AppUser u) {
        return userRepository.save(u);
    }

    public boolean existsByUniqueId(String username) {
        return userRepository.existsByUniqueId(username);
    }
}
