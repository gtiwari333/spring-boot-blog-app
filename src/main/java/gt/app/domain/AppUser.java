package gt.app.domain;

import lombok.Data;
import lombok.EqualsAndHashCode;
import org.springframework.security.core.userdetails.UserDetails;

import javax.persistence.*;
import javax.validation.constraints.Size;
import java.util.Collection;
import java.util.HashSet;
import java.util.Set;

@EqualsAndHashCode(callSuper = true)
@Entity
@Data
public class AppUser extends BaseEntity implements UserDetails {
    @Basic(fetch = FetchType.LAZY)
    @Lob
    byte[] avatar;

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

    @ManyToMany(fetch = FetchType.LAZY)
    @JoinTable(
        name = "user_authority",
        joinColumns = {@JoinColumn(name = "user_id", referencedColumnName = "id")},
        inverseJoinColumns = {@JoinColumn(name = "authority_name", referencedColumnName = "name")})
    private Set<Authority> authorities = new HashSet<>();

    @Column(nullable = false)
    private Boolean active = false;

    @Column(nullable = false)
    private Boolean accountNonExpired;

    @Column(nullable = false)
    private Boolean accountNonLocked;

    @Column(nullable = false)
    private Boolean credentialsNonExpired;

    private String activationKey;

    private String resetKey;

    @Override
    public Collection<Authority> getAuthorities() {
        return authorities;
    }

    @Override
    public String getPassword() {
        return password;
    }

    @Override
    public String getUsername() {
        return uniqueId;
    }

    @Override
    public boolean isAccountNonExpired() {
        return accountNonExpired;
    }

    @Override
    public boolean isAccountNonLocked() {
        return accountNonLocked;
    }

    @Override
    public boolean isCredentialsNonExpired() {
        return credentialsNonExpired;
    }

    @Override
    public boolean isEnabled() {
        return active;
    }

    public AppUser() {

    }

    public AppUser(String uniqueId, String firstName, String lastName, String email) {
        this.uniqueId = uniqueId;
        this.firstName = firstName;
        this.lastName = lastName;
        this.email = email;
        this.accountNonExpired = true;
        this.accountNonLocked = true;
        this.credentialsNonExpired = true;
        this.active = true;
    }

    @Override
    public String toString() {
        return "User{" +
            "firstName='" + firstName + '\'' +
            ", lastName='" + lastName + '\'' +
            ", email='" + email + '\'' +
            ", authorities=" + authorities +
            ", active=" + active +
            ", accountNonExpired=" + accountNonExpired +
            ", accountNonLocked=" + accountNonLocked +
            ", credentialsNonExpired=" + credentialsNonExpired +
            '}';
    }
}
