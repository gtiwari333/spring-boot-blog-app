package gt.app;

import gt.app.config.AppProperties;
import gt.app.config.Constants;
import gt.app.config.security.AppUserDetails;
import gt.app.modules.email.dto.EmailDto;
import gt.app.modules.note.dto.NoteCreateDto;
import gt.app.modules.note.dto.NoteEditDto;
import gt.app.modules.note.dto.NoteReadDto;
import gt.app.modules.user.AppPermissionEvaluatorService;
import gt.app.modules.user.dto.PasswordUpdateDTO;
import gt.app.modules.user.dto.UserDTO;
import lombok.extern.slf4j.Slf4j;
import org.springframework.aot.hint.MemberCategory;
import org.springframework.aot.hint.RuntimeHints;
import org.springframework.aot.hint.RuntimeHintsRegistrar;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.ImportRuntimeHints;
import org.springframework.core.env.Environment;
import org.springframework.data.domain.PageImpl;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.transaction.annotation.EnableTransactionManagement;

import java.net.InetAddress;
import java.net.UnknownHostException;
import java.util.Arrays;
import java.util.Map;

@SpringBootApplication
@Slf4j
@EnableConfigurationProperties(AppProperties.class)
@EnableTransactionManagement(proxyTargetClass = true)
@ImportRuntimeHints(MyRuntimeHints.class) //required for GraalVMNativeImage::
public class Application {

    public static void main(String[] args) throws UnknownHostException {

        var app = new SpringApplication(Application.class);
        app.setDefaultProperties(Map.of("spring.profiles.default", Constants.SPRING_PROFILE_DEVELOPMENT));
        Environment env = app.run(args).getEnvironment();

        log.info("""
                Access URLs:
                ----------------------------------------------------------
                \tLocal: \t\t\thttp://localhost:{}
                \tExternal: \t\thttp://{}:{}
                \tEnvironment: \t{}\s
                \t----------------------------------------------------------""",
            env.getProperty("server.port"),
            InetAddress.getLocalHost().getHostAddress(),
            env.getProperty("server.port"),
            Arrays.toString(env.getActiveProfiles())
        );
    }

}

//required for GraalVMNativeImage::
class MyRuntimeHints implements RuntimeHintsRegistrar {
    @Override
    public void registerHints(RuntimeHints hints, ClassLoader classLoader) {
        //record and dto classes -> get/set not found
        hints
            .reflection()
            .registerType(AppProperties.class, MemberCategory.values())
            .registerType(AppProperties.FileStorage.class, MemberCategory.values())
            .registerType(EmailDto.class, MemberCategory.values())
            .registerType(EmailDto.FileBArray.class, MemberCategory.values())
            .registerType(PasswordUpdateDTO.class, MemberCategory.values())
            .registerType(UserDTO.class, MemberCategory.values())
            .registerType(NoteCreateDto.class, MemberCategory.values())
            .registerType(NoteEditDto.class, MemberCategory.values())
            .registerType(NoteReadDto.class, MemberCategory.values())
            .registerType(NoteReadDto.FileInfo.class, MemberCategory.values())
            .registerType(AppUserDetails.class, MemberCategory.values())
            .registerType(UsernamePasswordAuthenticationToken.class, MemberCategory.values())
            .registerType(AppPermissionEvaluatorService.class, MemberCategory.values())
            .registerType(PageImpl.class, MemberCategory.values()); //EL1004E: Method call: Method getTotalElements() cannot be found on type org.springframework.data.domain.PageImpl


    }
}
