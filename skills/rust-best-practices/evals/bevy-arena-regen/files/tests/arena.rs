use std::time::Duration;

use arena::*;
use bevy::prelude::*;

#[derive(Resource, Default)]
struct Received(Vec<Hit>);

fn record_hits(mut hits: MessageReader<Hit>, mut received: ResMut<Received>) {
    received.0.extend(hits.read().copied());
}

#[test]
fn units_move_by_velocity_unless_stunned() {
    let mut app = App::new();
    app.init_resource::<Time>().add_systems(Update, move_units);
    let walker = app.world_mut().spawn((Position(Vec2::ZERO), Velocity(Vec2::new(10.0, 0.0)))).id();
    let stunned = app
        .world_mut()
        .spawn((Position(Vec2::ZERO), Velocity(Vec2::new(10.0, 0.0)), Stunned))
        .id();
    app.world_mut().resource_mut::<Time>().advance_by(Duration::from_secs(2));

    app.update();

    assert_eq!(app.world().get::<Position>(walker), Some(&Position(Vec2::new(20.0, 0.0))));
    assert_eq!(app.world().get::<Position>(stunned), Some(&Position(Vec2::ZERO)));
}

#[test]
fn enemies_in_range_hit_the_player() {
    let mut app = App::new();
    app.init_resource::<ArenaConfig>()
        .init_resource::<Received>()
        .add_message::<Hit>()
        .add_systems(Update, (contact_damage, record_hits).chain());
    let player = app.world_mut().spawn((Player, Position(Vec2::ZERO))).id();
    app.world_mut().spawn((Enemy, Position(Vec2::new(10.0, 0.0))));
    app.world_mut().spawn((Enemy, Position(Vec2::new(10.0, 0.0)), Stunned));
    app.world_mut().spawn((Enemy, Position(Vec2::new(100.0, 0.0))));

    app.update();

    let received = &app.world().resource::<Received>().0;
    assert_eq!(received.len(), 1);
    assert_eq!(received[0].target, player);
    assert_eq!(received[0].amount, 5);
}

#[test]
fn armor_reduces_damage_and_crits_add_half() {
    assert_eq!(damage_after_armor(10, 2, HitKind::Normal), 8);
    assert_eq!(damage_after_armor(10, 2, HitKind::Critical), 12);
    assert_eq!(damage_after_armor(1, 5, HitKind::Normal), 0);
}

#[test]
fn a_cleared_wave_spawns_the_next_one() {
    let mut app = App::new();
    app.init_resource::<ArenaConfig>()
        .insert_resource(Wave { number: 1, cleared: true })
        .add_systems(Update, spawn_wave);

    app.update();

    let enemies = app.world_mut().query_filtered::<(), With<Enemy>>().iter(app.world()).count();
    assert_eq!(enemies, 6);
    assert!(!app.world().resource::<Wave>().cleared);
}

#[test]
fn a_new_wave_starts_only_after_the_last_enemy_dies() {
    let mut app = App::new();
    app.init_resource::<ArenaConfig>()
        .init_resource::<Wave>()
        .add_systems(Update, (check_wave_cleared, spawn_wave).chain());

    for _ in 0..3 {
        app.update();
    }

    let enemies = app.world_mut().query_filtered::<(), With<Enemy>>().iter(app.world()).count();
    assert_eq!(enemies, 6);
    assert_eq!(app.world().resource::<Wave>().number, 1);
}

#[test]
fn the_plugin_runs_a_full_frame() {
    let mut app = App::new();
    app.init_resource::<Time>().add_plugins(ArenaPlugin);

    app.update();
    app.update();

    let players = app.world_mut().query_filtered::<(), With<Player>>().iter(app.world()).count();
    assert_eq!(players, 1);
}

#[test]
fn the_wave_counter_advances_when_no_enemies_are_left() {
    let mut app = App::new();
    app.init_resource::<Wave>().add_systems(Update, check_wave_cleared);

    app.update();

    let wave = app.world().resource::<Wave>();
    assert_eq!(wave.number, 1);
    assert!(wave.cleared);
}
