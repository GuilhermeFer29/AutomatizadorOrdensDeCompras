import { LayoutDashboard, Bot, ShoppingCart, Package } from "lucide-react";
import { NavLink } from "react-router-dom";
import { cn } from "@/lib/utils";

const navigation = [
  { name: "Dashboard", href: "/", icon: LayoutDashboard },
  { name: "Hub de Agentes", href: "/agents", icon: Bot },
  { name: "Ordens de Compra", href: "/orders", icon: ShoppingCart },
  { name: "Catálogo", href: "/catalog", icon: Package },
];

export function Sidebar() {
  return (
    <aside className="w-64 bg-card border-r border-border min-h-screen">
      <div className="p-6">
        <h1 className="text-xl font-semibold text-foreground">
          Sistema de Automação
        </h1>
        <p className="text-xs text-muted-foreground mt-1">
          Ordens Inteligentes
        </p>
      </div>

      <nav className="px-3 space-y-1">
        {navigation.map((item) => (
          <NavLink
            key={item.name}
            to={item.href}
            end={item.href === "/"}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors",
                isActive
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:bg-secondary hover:text-foreground"
              )
            }
          >
            <item.icon className="h-5 w-5" />
            {item.name}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
