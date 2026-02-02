package gt.app.web.rest;

import gt.app.config.Constants;
import io.quarkus.security.Authenticated;
import jakarta.annotation.security.RolesAllowed;
import jakarta.ws.rs.GET;
import jakarta.ws.rs.Path;

@Path("/api")
@Authenticated
public class ApiResource {

    @GET
    @Path("/admin")
    @RolesAllowed(Constants.ROLE_ADMIN)
    public String adminEndpoint() {
        return "Admin access";
    }

    @GET
    @Path("/user")
    @RolesAllowed(Constants.ROLE_USER)
    public String userEndpoint() {
        return "User access";
    }
}
