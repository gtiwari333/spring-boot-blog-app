package gt.app.web.rest;

import gt.app.config.Constants;
import gt.app.modules.email.dto.EmailDto;
import gt.app.modules.email.EmailService;
import io.quarkus.arc.profile.IfBuildProfile;
import jakarta.ws.rs.GET;
import jakarta.ws.rs.POST;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.core.Response;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotNull;

import java.util.Map;

@RequiredArgsConstructor
@Slf4j
@IfBuildProfile(anyOf = {Constants.SPRING_PROFILE_DEVELOPMENT, Constants.SPRING_PROFILE_TEST})
@Path("")
public class HelloResource {
    private final EmailService emailService;

    @GET
    @Path("/debug/hello")
    public Map<String, String> sayHello() {
        return Map.of("hello", "world");
    }

    @POST
    @Path("/debug/sendEmail")
    public Response sendEmailWithAttachments(@Valid @NotNull EmailDto email) {
        log.debug("Sending email ...");

        emailService.sendEmail(email);

        return Response.ok().build();
    }
}
