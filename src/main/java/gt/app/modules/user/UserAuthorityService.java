package gt.app.modules.user;

import gt.app.config.security.AppUserDetails;
import gt.app.domain.Note;
import gt.app.domain.User;
import gt.app.modules.note.NoteService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@RequiredArgsConstructor
@Slf4j
//@Transactional(readOnly = true) idk why it needs to be commented.. i was getting following error:
//Caused by: org.springframework.beans.factory.BeanCreationException: Error creating bean with name 'userAuthorityService' defined in class path resource [gt/app/modules/user/UserAuthorityService.class]: Initialization of bean failed; nested exception is com.oracle.svm.core.jdk.UnsupportedFeatureError: Proxy class defined by interfaces [interface org.springframework.aop.SpringProxy, interface org.springframework.aop.framework.Advised, interface org.springframework.core.DecoratingProxy] not found. Generating proxy classes at runtime is not supported. Proxy classes need to be defined at image build time by specifying the list of interfaces that they implement. To define proxy classes use -H:DynamicProxyConfigurationFiles=<comma-separated-config-files> and -H:DynamicProxyConfigurationResources=<comma-separated-config-resources> options.
//tried updating the proxy-config, but it got overridden by spring-boot:build-image goal
public class UserAuthorityService {

    private final NoteService noteService;

    public boolean hasAccess(AppUserDetails curUser, Long id, String entity) {

        if (curUser.isSystemAdmin()) {
            return true;
        }

        if (User.class.getSimpleName().equalsIgnoreCase(entity)) {
            return id.equals(curUser.getId());
        }


        if (Note.class.getSimpleName().equalsIgnoreCase(entity)) {

            Long createdById = noteService.findCreatedByUserIdById(id);

            return createdById.equals(curUser.getId());
        }


        /*
        add more rules
         */

        return false;
    }

}
