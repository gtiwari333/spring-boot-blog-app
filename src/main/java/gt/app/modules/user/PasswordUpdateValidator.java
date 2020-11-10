package gt.app.modules.user;

import gt.app.config.security.AppUserDetails;
import lombok.RequiredArgsConstructor;
import org.apache.commons.lang3.StringUtils;
import org.springframework.stereotype.Component;
import org.springframework.validation.Errors;
import org.springframework.validation.Validator;

@RequiredArgsConstructor
@Component
public class PasswordUpdateValidator implements Validator {

    final UserRepository userRepository;

    @Override
    public boolean supports(Class clazz) {
        return PasswordUpdateDTO.class.equals(clazz);
    }

    @Override
    public void validate(Object target, Errors errors) {
    }

    public void validate(Object target, Errors errors, AppUserDetails principal) {

        PasswordUpdateDTO toCreate = (PasswordUpdateDTO) target;

        if (StringUtils.containsIgnoreCase(toCreate.getPwdPlaintext(), principal.getUsername()) || StringUtils.containsIgnoreCase(principal.getUsername(), toCreate.getPwdPlaintext())) {
            errors.rejectValue("pwdPlaintext", "user.weakpwd", "Weak password, choose another");
        }

    }

}
