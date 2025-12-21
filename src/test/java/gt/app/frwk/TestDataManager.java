package gt.app.frwk;

import gt.app.DataCreator;
import jakarta.persistence.EntityManagerFactory;
import lombok.RequiredArgsConstructor;
import org.hibernate.engine.spi.SessionFactoryImplementor;
import org.springframework.beans.factory.InitializingBean;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@RequiredArgsConstructor
public class TestDataManager implements InitializingBean {
    final EntityManagerFactory entityManagerFactory;
    final DataCreator dataCreator;

    @Override
    public void afterPropertiesSet() {
    }

    @Transactional
    public void truncateTablesAndRecreate() {
        entityManagerFactory
            .unwrap(SessionFactoryImplementor.class)
            .getSchemaManager()
            .truncateMappedObjects();
        dataCreator.initData();
    }

}
