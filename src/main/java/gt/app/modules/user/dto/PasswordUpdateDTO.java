package gt.app.modules.user.dto;

import javax.validation.constraints.NotNull;
import javax.validation.constraints.Size;

public record PasswordUpdateDTO(@NotNull @Size(min = 5, max = 50) String pwdPlainText) {
    public static PasswordUpdateDTO of() {
        return new PasswordUpdateDTO("");
    }
}
