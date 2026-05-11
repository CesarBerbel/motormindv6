# Generated for MotorMindV6 Auto Mec Bandeirantes design system settings.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("workshop", "0028_alter_workorderevent_event_type")]

    operations = [
        migrations.AddField(model_name="workshopprofile", name="ui_theme_mode", field=models.CharField(choices=[("light", "Claro"), ("dark", "Escuro"), ("auto", "Automático")], default="light", max_length=20, verbose_name="Tema da interface")),
        migrations.AddField(model_name="workshopprofile", name="ui_primary_color", field=models.CharField(default="#0d6efd", max_length=20, verbose_name="Cor primária")),
        migrations.AddField(model_name="workshopprofile", name="ui_accent_color", field=models.CharField(default="#fd7e14", max_length=20, verbose_name="Cor de destaque")),
        migrations.AddField(model_name="workshopprofile", name="ui_sidebar_color", field=models.CharField(default="#172033", max_length=20, verbose_name="Cor do menu lateral")),
        migrations.AddField(model_name="workshopprofile", name="ui_form_density", field=models.CharField(choices=[("compact", "Compacto"), ("comfortable", "Confortável"), ("spacious", "Espaçoso")], default="comfortable", max_length=20, verbose_name="Densidade dos formulários")),
        migrations.AddField(model_name="workshopprofile", name="ui_table_density", field=models.CharField(choices=[("compact", "Compacto"), ("comfortable", "Confortável")], default="comfortable", max_length=20, verbose_name="Densidade das tabelas")),
        migrations.AddField(model_name="workshopprofile", name="ui_card_radius", field=models.CharField(choices=[("soft", "Suave"), ("rounded", "Arredondado"), ("pill", "Muito arredondado")], default="rounded", max_length=20, verbose_name="Raio dos cards e campos")),
        migrations.AddField(model_name="workshopprofile", name="ui_button_style", field=models.CharField(choices=[("solid", "Preenchido"), ("soft", "Suave"), ("outline", "Contorno")], default="solid", max_length=20, verbose_name="Estilo dos botões primários")),
        migrations.AddField(model_name="workshopprofile", name="ui_form_layout", field=models.CharField(choices=[("grouped", "Agrupado por seções"), ("flat", "Plano"), ("wizard", "Abas/etapas")], default="grouped", max_length=20, verbose_name="Layout padrão dos formulários")),
        migrations.AddField(model_name="workshopprofile", name="ui_show_required_hint", field=models.BooleanField(default=True, verbose_name="Exibir dica em campos obrigatórios")),
        migrations.AddField(model_name="workshopprofile", name="ui_enable_motion", field=models.BooleanField(default=True, verbose_name="Ativar microinterações")),
    ]
