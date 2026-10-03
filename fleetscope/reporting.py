import io
import json
import zipfile


def bundle(estimates, assessment, validation, metrics, contributions, config):
    memory = io.BytesIO()
    with zipfile.ZipFile(memory, 'w', zipfile.ZIP_DEFLATED) as z:
        for name, df in [
            ('estimates', estimates),
            ('source_assessment', assessment),
            ('validation', validation),
            ('contributions', contributions),
        ]:
            z.writestr(name + '.csv', df.to_csv(index=False))
        z.writestr('metrics.json', json.dumps(metrics, indent=2, allow_nan=False))
        z.writestr('configuration.json', json.dumps(config, indent=2))
        z.writestr(
            'REPORT.md',
            '# FleetScope synthetic demonstration\n\n'
            'Model-based 95% uncertainty intervals are heuristic, not calibrated statistical confidence intervals. '
            'Sources may be correlated. Coverage correction assumes the observed sample is representative. '
            'See README for equations and limitations.\n',
        )
    return memory.getvalue()
