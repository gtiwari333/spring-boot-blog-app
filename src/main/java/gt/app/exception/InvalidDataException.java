package gt.app.exception;

public class InvalidDataException extends RuntimeException {

    private static final long serialVersionUID = 1L;

    public InvalidDataException(String message) {
        super(message);
    }

    public InvalidDataException(String message, Throwable e) {
        super(message, e);
    }
}
