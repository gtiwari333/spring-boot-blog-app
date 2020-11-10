package gt.app.modules.user;

import lombok.Data;

import javax.validation.constraints.NotNull;
import javax.validation.constraints.Size;

@Data
public class PasswordUpdateDTO {

    @NotNull
    @Size(min = 5, max = 50)
    private String pwdPlaintext;
}
