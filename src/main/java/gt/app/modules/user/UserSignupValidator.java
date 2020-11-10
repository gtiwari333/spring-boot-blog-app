package gt.app.modules.user;

import lombok.RequiredArgsConstructor;
import org.apache.commons.lang3.StringUtils;
import org.springframework.stereotype.Component;
import org.springframework.validation.Errors;
import org.springframework.validation.Validator;

@RequiredArgsConstructor
@Component
public class UserSignupValidator implements Validator {

    final UserRepository userRepository;

    @Override
    public boolean supports(Class clazz) {
        return UserSignUpDTO.class.equals(clazz);
    }

    @Override
    public void validate(Object target, Errors errors) {
        UserSignUpDTO toCreate = (UserSignUpDTO) target;

        if (StringUtils.containsIgnoreCase(toCreate.getPwdPlaintext(), toCreate.getUniqueId()) || StringUtils.containsIgnoreCase(toCreate.getUniqueId(), toCreate.getPwdPlaintext())) {
            errors.rejectValue("pwdPlaintext", "user.weakpwd", "Weak password, choose another");
        }

        if (userRepository.existsByUniqueId(toCreate.getUniqueId())) {
            errors.rejectValue("uniqueId", "user.alreadyexists", "Username " + toCreate.getUniqueId() + " already exists");
        }
    }

}
