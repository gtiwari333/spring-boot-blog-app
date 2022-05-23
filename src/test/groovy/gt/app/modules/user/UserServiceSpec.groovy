package gt.app.modules.user

import gt.app.config.Constants
import gt.app.domain.AppUser
import gt.app.modules.email.EmailService
import gt.app.modules.user.dto.UserSignUpDTO
import org.springframework.security.crypto.password.NoOpPasswordEncoder
import org.springframework.security.crypto.password.PasswordEncoder
import spock.lang.Specification

class UserServiceSpec extends Specification {

    UserRepository userRepository
    PasswordEncoder passwordEncoder
    AuthorityService authorityService
    EmailService emailService

    UserService userService

    def setup() {
        userRepository = Mock()
        passwordEncoder = NoOpPasswordEncoder.getInstance()
        authorityService = Mock()
        emailService = Mock()
        userService = new UserService(userRepository, passwordEncoder, authorityService, emailService)
    }

    def 'create user'() {
        given:
        def toCreate = new UserSignUpDTO(uniqueId: 'U01', pwdPlaintext: 'pass', lastName: 'last1', firstName: 'first', email: 'gg@email')

        when:
        AppUser user = userService.create(toCreate)

        then:
        user.password == toCreate.pwdPlaintext //noop encoder
        user.uniqueId == toCreate.uniqueId
        user.email == toCreate.email
        1 * authorityService.findByNameIn(Constants.ROLE_USER)
        1 * userRepository.save(_)
        1 * emailService.sendEmail(_)
        0 * _
    }
}
