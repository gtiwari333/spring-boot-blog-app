package gt.app.exception;

import java.io.Serial;

public class InternalServerErrorException extends RuntimeException {

    @Serial
    private static final long serialVersionUID = 1L;

    public InternalServerErrorException(String message) {
        super(message);
    }

    public InternalServerErrorException(String message, Throwable e) {
        super(message, e);
    }
}
