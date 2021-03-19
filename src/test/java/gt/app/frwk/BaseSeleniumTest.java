package gt.app.frwk;

import com.codeborne.selenide.Browsers;
import com.codeborne.selenide.Configuration;
import gt.app.config.Constants;
import org.junit.jupiter.api.BeforeAll;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.DEFINED_PORT, properties = "server.port=8081")
@ActiveProfiles(Constants.SPRING_PROFILE_TEST)
public abstract class BaseSeleniumTest {

    @BeforeAll
    public static void init() {
        Configuration.headless = false;
        Configuration.browser = Browsers.FIREFOX;


        Configuration.baseUrl = "http://localhost:8081";
    }
}
