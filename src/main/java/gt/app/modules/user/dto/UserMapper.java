package gt.app.modules.user.dto;

import gt.app.domain.AppUser;
import gt.app.domain.Authority;
import org.mapstruct.Mapper;
import org.mapstruct.Mapping;

import java.util.Collection;
import java.util.List;
import java.util.stream.Collectors;

@Mapper(componentModel = "spring")
public interface UserMapper {

    @Mapping(source = "uniqueId", target = "login")
    UserDTO userToUserDto(AppUser user);

    default List<String> mapAuthorities(Collection<Authority> authorities) {
        return authorities.stream().map(Authority::getName).collect(Collectors.toList());
    }

}
