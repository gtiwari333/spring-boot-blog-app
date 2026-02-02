package gt.app.web.rest;

import gt.app.config.security.AppUserDetails;
import gt.app.config.security.SecurityUtils;
import jakarta.ws.rs.GET;
import jakarta.ws.rs.Path;
import lombok.RequiredArgsConstructor;

@Path("/api")
@RequiredArgsConstructor
public class UserResource {

    @GET
    @Path("/account")
    public AppUserDetails getAccount() {
        return SecurityUtils.getCurrentUserDetails();
    }
}
