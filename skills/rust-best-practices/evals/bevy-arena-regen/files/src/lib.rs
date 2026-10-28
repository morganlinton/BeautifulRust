//! A wave-based arena: the player fights waves of enemies that walk toward them.

use bevy::prelude::*;

/// Hit points. An entity at zero is dead and gets despawned.
#[derive(Component, Debug, Clone, Copy, PartialEq, Eq)]
pub struct Health(pub u32);

/// Flat damage reduction applied to every hit.
#[derive(Component, Debug, Clone, Copy, PartialEq, Eq)]
pub struct Armor(pub u32);

/// World position in pixels.
#[derive(Component, Debug, Clone, Copy, PartialEq)]
pub struct Position(pub Vec2);

/// Movement in pixels per second.
#[derive(Component, Debug, Clone, Copy, PartialEq)]
pub struct Velocity(pub Vec2);

/// Marks the player.
#[derive(Component, Debug)]
pub struct Player;

/// Marks an enemy.
#[derive(Component, Debug)]
pub struct Enemy;

/// A stunned unit neither moves nor deals contact damage.
#[derive(Component, Debug)]
pub struct Stunned;

/// Damage queued against an entity this frame.
#[derive(Message, Debug, Clone, Copy)]
pub struct Hit {
    pub target: Entity,
    pub amount: u32,
    pub kind: HitKind,
}

/// Whether a hit is a normal or a critical one.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum HitKind {
    Normal,
    /// Deals half again as much damage.
    Critical,
}

/// Wave progress.
#[derive(Resource, Debug, Default)]
pub struct Wave {
    pub number: u32,
    pub cleared: bool,
}

/// Points for kills.
#[derive(Resource, Debug, Default)]
pub struct Score(pub u32);

/// Tuning values for the arena.
#[derive(Resource, Debug, Clone)]
pub struct ArenaConfig {
    pub enemies_per_wave: u32,
    pub enemy_health: u32,
    pub contact_damage: u32,
    pub contact_range: f32,
    pub spawn_radius: f32,
    pub enemy_speed: f32,
}

impl Default for ArenaConfig {
    fn default() -> Self {
        Self {
            enemies_per_wave: 6,
            enemy_health: 30,
            contact_damage: 5,
            contact_range: 16.0,
            spawn_radius: 200.0,
            enemy_speed: 40.0,
        }
    }
}

/// Adds the arena's resources and systems.
pub struct ArenaPlugin;

impl Plugin for ArenaPlugin {
    fn build(&self, app: &mut App) {
        app.init_resource::<Wave>()
            .init_resource::<Score>()
            .init_resource::<ArenaConfig>()
            .add_message::<Hit>()
            .add_systems(Startup, spawn_player)
            .add_systems(Update, (move_units, contact_damage, apply_hits, stun_wounded).chain())
            .add_systems(Update, (check_wave_cleared, spawn_wave).chain());
    }
}

/// Spawns the player at the center of the arena.
pub fn spawn_player(mut commands: Commands) {
    commands.spawn((
        Player,
        Health(100),
        Armor(2),
        Position(Vec2::ZERO),
        Velocity(Vec2::ZERO),
    ));
}

/// Moves every unit that isn't stunned.
pub fn move_units(time: Res<Time>, mut units: Query<(&mut Position, &Velocity), Without<Stunned>>) {
    let dt = time.delta_secs();
    for (mut position, velocity) in &mut units {
        position.0 += velocity.0 * dt;
    }
}

/// Enemies touching the player hit them. Does nothing once the player is gone.
pub fn contact_damage(
    config: Res<ArenaConfig>,
    player: Single<(Entity, &Position), With<Player>>,
    enemies: Query<&Position, (With<Enemy>, Without<Stunned>)>,
    mut hits: MessageWriter<Hit>,
) {
    let (player, player_position) = *player;
    for position in &enemies {
        if position.0.distance(player_position.0) <= config.contact_range {
            hits.write(Hit {
                target: player,
                amount: config.contact_damage,
                kind: HitKind::Normal,
            });
        }
    }
}

/// Applies this frame's hits, despawns whatever dies, and scores enemy kills.
pub fn apply_hits(
    mut commands: Commands,
    mut hits: MessageReader<Hit>,
    mut players: Query<(&mut Health, Option<&Armor>), (With<Player>, Without<Enemy>)>,
    mut enemies: Query<(&mut Health, Option<&Armor>), (With<Enemy>, Without<Player>)>,
    mut score: ResMut<Score>,
) {
    for hit in hits.read() {
        let (mut health, armor) = if let Ok(target) = players.get_mut(hit.target) {
            target
        } else if let Ok(target) = enemies.get_mut(hit.target) {
            target
        } else {
            continue;
        };
        let was_alive = health.0 > 0;
        let dealt = damage_after_armor(hit.amount, armor.map_or(0, |a| a.0), hit.kind);
        health.0 = health.0.saturating_sub(dealt);
        if was_alive && health.0 == 0 {
            if enemies.contains(hit.target) {
                score.0 += 10;
            }
            commands.entity(hit.target).despawn();
        }
    }
}

/// Enemies hurt below a quarter of their health, plus their armor, are stunned for the
/// rest of the wave.
pub fn stun_wounded(
    mut commands: Commands,
    config: Res<ArenaConfig>,
    wounded: Query<(Entity, &Health, Option<&Armor>), (With<Enemy>, Without<Stunned>, Changed<Health>)>,
) {
    for (entity, health, armor) in &wounded {
        let threshold = config.enemy_health / 4 + armor.map_or(0, |a| a.0);
        if health.0 > 0 && health.0 < threshold {
            commands.entity(entity).insert(Stunned);
        }
    }
}

/// Damage left after armor; critical hits deal half again as much, rounded down.
pub fn damage_after_armor(raw: u32, armor: u32, kind: HitKind) -> u32 {
    let base = raw.saturating_sub(armor);
    match kind {
        HitKind::Normal => base,
        HitKind::Critical => base.saturating_add(base / 2),
    }
}

/// Spawns the next wave in a ring around the player once the last one is cleared.
pub fn spawn_wave(mut commands: Commands, config: Res<ArenaConfig>, mut wave: ResMut<Wave>) {
    if !wave.cleared {
        return;
    }
    wave.cleared = false;
    for i in 0..config.enemies_per_wave {
        let direction = Vec2::from_angle(i as f32 / config.enemies_per_wave as f32 * std::f32::consts::TAU);
        commands.spawn((
            Enemy,
            Health(config.enemy_health),
            Position(direction * config.spawn_radius),
            Velocity(-direction * config.enemy_speed),
        ));
    }
}

/// Starts the next wave once no enemies are left.
pub fn check_wave_cleared(enemies: Query<(), With<Enemy>>, mut wave: ResMut<Wave>) {
    if !wave.cleared && enemies.is_empty() {
        wave.number += 1;
        wave.cleared = true;
    }
}
