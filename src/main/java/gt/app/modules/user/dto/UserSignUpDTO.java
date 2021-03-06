package gt.app.modules.user.dto;

import lombok.Data;
import lombok.EqualsAndHashCode;

import javax.validation.constraints.NotNull;
import javax.validation.constraints.Size;

@EqualsAndHashCode(callSuper = true)
@Data
public class UserSignUpDTO extends UserProfileUpdateDTO {

    @NotNull
    @Size(min = 5, max = 20)
    private String uniqueId;

    @NotNull
    @Size(min = 5, max = 50)
    private String pwdPlaintext;
}
