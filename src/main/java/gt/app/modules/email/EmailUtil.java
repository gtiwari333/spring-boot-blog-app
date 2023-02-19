package gt.app.modules.email;

import gt.app.exception.InvalidDataException;
import lombok.experimental.UtilityClass;

import jakarta.mail.internet.AddressException;
import jakarta.mail.internet.InternetAddress;
import java.util.Collection;
import java.util.function.Function;

@UtilityClass
public class EmailUtil {

    static Function<String, InternetAddress> toInternetAddr() {
        return it -> {
            try {
                return new InternetAddress(it);
            } catch (AddressException e) {
                throw new InvalidDataException("Invalid email address " + it, e);
            }
        };
    }

    static InternetAddress[] toInetArray(Collection<String> tos) {
        if (tos == null) {
            return new InternetAddress[0];
        }
        return tos.stream().map(EmailUtil.toInternetAddr()).toArray(InternetAddress[]::new);
    }

}
