package gt.app.config.security;

import lombok.Getter;

import java.security.Principal;
import java.util.Set;

@Getter
public class AppUserDetails implements Principal {

    private final Long id;
    private final String username; // This is the username
    private final String firstName;
    private final String lastName;
    private final String email;
    private final Set<String> roles;

    public AppUserDetails(Long id, String username, String email, String firstName, String lastName, Set<String> roles) {
        this.id = id;
        this.username = username;
        this.firstName = firstName;
        this.lastName = lastName;
        this.email = email;
        this.roles = roles;
    }

    @Override
    public String getName() {
        return username;
    }

    public boolean isUser() {
        return roles.contains("ROLE_USER");
    }

    public boolean isSystemAdmin() {
        return roles.contains("ROLE_ADMIN");
    }
}
