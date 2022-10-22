package gt.app;

import gt.app.config.Constants;
import gt.app.web.rest.HelloResource;
import lombok.extern.slf4j.Slf4j;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;

import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

@SpringBootTest
@ActiveProfiles(Constants.SPRING_PROFILE_TEST)
class ApplicationTest {

    @Autowired
    private HelloResource webController;
    @Test
    void contextLoads() {
        assertTrue(true, "Context loads !!!");
        assertNotNull(webController);
    }

}


