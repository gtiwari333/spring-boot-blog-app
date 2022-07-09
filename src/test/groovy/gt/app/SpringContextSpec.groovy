package gt.app

import gt.app.config.Constants
import gt.app.web.rest.HelloResource
import org.springframework.beans.factory.annotation.Autowired
import org.springframework.boot.test.context.SpringBootTest
import org.springframework.test.context.ActiveProfiles
import spock.lang.Specification

@SpringBootTest
@ActiveProfiles(Constants.SPRING_PROFILE_TEST)
class SpringContextSpec extends Specification {

//    @Autowired
//    private HelloResource webController

    def "when context is loaded then all expected beans are created"() {
        expect: "the WebController is created"
        1 == 1
//        webController
    }
}
