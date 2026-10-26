#![deny(warnings)]
use std::cell::RefCell;
use std::collections::HashMap;
use std::rc::Rc;

#[derive(Debug, Clone)]
pub enum InventoryError {
    NotFound,
    Invalid,
    Io,
    Parse,
    Other(String),
}

#[derive(Clone)]
pub struct Item {
    pub name: String,
    pub qty: i64,
    pub price_cents: i64,
    pub is_perishable: bool,
}

pub struct Inventory {
    items: Rc<RefCell<HashMap<String, Item>>>,
}

impl Inventory {
    pub fn new() -> Rc<RefCell<Inventory>> {
        Rc::new(RefCell::new(Inventory {
            items: Rc::new(RefCell::new(HashMap::new())),
        }))
    }

    pub fn get_item(&self, name: &String) -> Option<Item> {
        if self.items.borrow().get(name).is_some() {
            Some(self.items.borrow().get(name).unwrap().clone())
        } else {
            None
        }
    }

    pub fn add_item(&self, name: String, qty: i64, price: i64, perishable: bool) -> Result<(), InventoryError> {
        if qty < 0 || price < 0 {
            return Err(InventoryError::Invalid);
        }
        let item = Item { name: name.clone(), qty: qty, price_cents: price, is_perishable: perishable };
        self.items.borrow_mut().insert(name, item);
        Ok(())
    }

    pub fn total_value(&self, names: &Vec<String>) -> i64 {
        let mut total = 0;
        for n in names {
            let item = self.items.borrow().get(n).unwrap().clone();
            total += item.qty * item.price_cents;
        }
        total
    }

    pub fn restock(&self, name: &String, amount: i64) -> Result<(), InventoryError> {
        if self.items.borrow().get(name).is_some() {
            let mut item = self.items.borrow().get(name).unwrap().clone();
            item.qty += amount;
            self.items.borrow_mut().insert(name.clone(), item);
            Ok(())
        } else {
            Err(InventoryError::NotFound)
        }
    }

    pub fn parse_line(line: &String) -> Result<Item, InventoryError> {
        let parts: Vec<&str> = line.split(',').collect();
        if parts.len() != 4 {
            return Err(InventoryError::Parse);
        }
        let qty = parts[1].trim().parse::<i64>().unwrap();
        let price = parts[2].trim().parse::<i64>().unwrap();
        let perishable = if parts[3].trim() == "true" { true } else { false };
        Ok(Item { name: parts[0].trim().to_string(), qty: qty, price_cents: price, is_perishable: perishable })
    }

    pub fn load(path: &String) -> Result<Rc<RefCell<Inventory>>, InventoryError> {
        let text = std::fs::read_to_string(path).unwrap();
        let inv = Inventory::new();
        for line in text.lines() {
            if line.trim().len() == 0 {
                continue;
            }
            let item = Inventory::parse_line(&line.to_string())?;
            inv.borrow().items.borrow_mut().insert(item.name.clone(), item);
        }
        Ok(inv)
    }

    pub fn report(&self, verbose: bool) -> String {
        let mut s = String::new();
        for (k, v) in self.items.borrow().iter() {
            s = s + &k + ": " + &v.qty.to_string() + "\n";
            if verbose {
                s = s + "  price=" + &v.price_cents.to_string() + " perishable=" + &v.is_perishable.to_string() + "\n";
            }
        }
        s
    }
}
