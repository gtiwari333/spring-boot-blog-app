package gt.app.modules.user;

import gt.app.config.Constants;
import gt.app.config.security.AppUserDetails;
import gt.app.config.security.SecurityUtils;
import gt.app.domain.User;
import gt.app.exception.RecordNotFoundException;
import gt.app.modules.email.EmailDto;
import gt.app.modules.email.EmailService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.Optional;
import java.util.Set;

@Service
@Transactional
@RequiredArgsConstructor
@Slf4j
public class UserService {

    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;
    private final AuthorityService authorityService;
    private final EmailService emailService;

    @Transactional(readOnly = true)
    public Optional<User> getCurrentUserWithAuthorities() {
        return SecurityUtils.getCurrentUserLogin().flatMap(userRepository::findOneWithAuthoritiesByUniqueId);
    }

    public Page<User> findAll(Pageable pageable) {
        return userRepository.findAllByActiveIsTrue(pageable);
    }

    public Optional<User> findById(Long id) {
        return userRepository.findByIdAndActiveIsTrue(id);
    }

    public void update(UserProfileUpdateDTO toUpdate, AppUserDetails userDetails) {
        User user = userRepository.findOneByUniqueId(userDetails.getUsername())
            .orElseThrow(() -> new RecordNotFoundException("User", "login", userDetails.getUsername()));

        user.setFirstName(toUpdate.getFirstName());
        user.setLastName(toUpdate.getLastName());
        user.setEmail(toUpdate.getEmail());

        userRepository.save(user);
    }

    public void updatePassword(PasswordUpdateDTO toUpdate, AppUserDetails userDetails) {
        User user = userRepository.findOneByUniqueId(userDetails.getUsername())
            .orElseThrow(() -> new RecordNotFoundException("User", "login", userDetails.getUsername()));

        user.setPassword(passwordEncoder.encode(toUpdate.getPwdPlaintext()));
        userRepository.save(user);
    }

    public User create(UserSignUpDTO toCreate) {

        var user = new User(toCreate.getUniqueId(), toCreate.getFirstName(), toCreate.getLastName(), toCreate.getEmail());

        user.setPassword(passwordEncoder.encode(toCreate.getPwdPlaintext()));

        user.setAuthorities(authorityService.findByNameIn(Constants.ROLE_USER));

        userRepository.save(user);

        EmailDto dto = EmailDto.builder()
            .from("system@noteapp")
            .to(Set.of(user.getEmail()))
            .subject("NoteApp Account Created!")
            .content("Thanks for signing up.")
            .build();

        emailService.sendEmail(dto);

        return user;
    }

    public void delete(Long id) {
        User author = userRepository.findByIdAndActiveIsTrue(id)
            .orElseThrow(() -> new RecordNotFoundException("User", "id", id));

        author.setActive(false);
        userRepository.save(author);
    }

    public Optional<User> findWithAuthoritiesByEmail(String email) {
        return userRepository.findOneWithAuthoritiesByUniqueId(email);
    }

    public User save(User u) {
        return userRepository.save(u);
    }
}
