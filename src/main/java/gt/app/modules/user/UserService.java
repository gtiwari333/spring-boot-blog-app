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
import io.quarkus.elytron.security.common.BcryptUtil; // Quarkus standard for Bcrypt
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;
import jakarta.transaction.Transactional;
import lombok.RequiredArgsConstructor;

import java.util.List;
import java.util.Set;

@ApplicationScoped
@RequiredArgsConstructor
public class UserService {

    private final UserRepository userRepository;
    private final AuthorityService authorityService;
    private final EmailService emailService;
    private final LiteUserRepository liteUserRepository;

    @Transactional
    public void update(UserProfileUpdateDTO toUpdate, AppUserDetails userDetails) {
        LiteUser user = liteUserRepository.findOneByUniqueId(userDetails.getUsername())
            .orElseThrow(() -> new RecordNotFoundException("User", "login", userDetails.getUsername()));

        user.setFirstName(toUpdate.getFirstName());
        user.setLastName(toUpdate.getLastName());
        user.setEmail(toUpdate.getEmail());

        // In Panache, changes to attached entities are auto-flushed at end of transaction.
        // Explicit .save() is usually not needed if using PanacheRepository.persist().
    }

    @Transactional
    public void updatePassword(PasswordUpdateDTO toUpdate, AppUserDetails userDetails) {
        LiteUser user = liteUserRepository.findOneByUniqueId(userDetails.getUsername())
            .orElseThrow(() -> new RecordNotFoundException("User", "login", userDetails.getUsername()));

        // Quarkus uses BcryptUtil for simple encoding
        user.setPassword(BcryptUtil.bcryptHash(toUpdate.pwdPlainText()));
    }

    @Transactional
    public AppUser create(UserSignUpDTO toCreate) {
        var user = new AppUser(toCreate.getUniqueId(), toCreate.getFirstName(), toCreate.getLastName(), toCreate.getEmail());

        user.setPassword(BcryptUtil.bcryptHash(toCreate.getPwdPlaintext()));
        user.setAuthorities(authorityService.findByNameIn(Constants.ROLE_USER));

        userRepository.persist(user);

        EmailDto dto = EmailDto.of("system@noteapp", List.of(user.getEmail()),
            "NoteApp Account Created!",
            "Thanks for signing up.");

        emailService.sendEmail(dto);

        return user;
    }

    @Transactional
    public void delete(Long id) {
        LiteUser author = liteUserRepository.findByIdAndActiveIsTrue(id)
            .orElseThrow(() -> new RecordNotFoundException("User", "id", id));

        author.setActive(Boolean.FALSE);
    }

    @Transactional
    public AppUser save(AppUser u) {
        userRepository.persist(u);
        return u;
    }

    public boolean existsByUniqueId(String username) {
        return userRepository.existsByUniqueId(username);
    }
}
