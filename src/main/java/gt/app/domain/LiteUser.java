package gt.app.domain;

import lombok.Data;
import lombok.EqualsAndHashCode;

import jakarta.persistence.*;
import jakarta.validation.constraints.Size;

@EqualsAndHashCode(callSuper = true)
@Entity
@Table(name="APP_USER")
@Data
@SuppressWarnings("DirectReturn")
public class LiteUser extends BaseEntity {

    @Column(nullable = false)
    @Size(min = 2, max = 30)
    private String firstName;

    @Size(max = 30)
    private String lastName;

    @Column(length = 254, unique = true, nullable = false)
    private String email;

    @Column(nullable = false, unique = true)
    @Size(min = 5, max = 20)
    private String uniqueId;

    @Column(name = "password_hash", length = 60)
    private String password;

    @Column(nullable = false)
    private Boolean active = false;

}
